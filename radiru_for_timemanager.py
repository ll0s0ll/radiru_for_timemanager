#! /usr/bin/env python
# -*- coding: utf-8 -*-
u"""
NHKラジオの聴取をTimeManagerにスケジュールするためのプログラムです。

標準では繰り返し実行されます。繰り返す回数、間隔はオプションで設定できます。

EXAMPLE
NHKラジオ第一 仙台放送局のすっぴんをスケジュールする。
$ ./radiru_for_timemanager.py sendai r1 "5 8 * * 1-5" 13500 "すっぴん"

内部で以下のプログラムを呼び出しています。
[play_radiru.sh]
https://github.com/ll0s0ll/play_radiru

[TimeManager]
https://github.com/ll0s0ll/TimeManager
"""
from __future__ import print_function

import argparse
import errno
import logging
import os
import signal
import subprocess
import sys
import time


CHANNELS = ('r1', 'r2', 'fm')
REGIONS = ('sapporo', 'sendai', 'tokyo', 'nagoya', 'osaka', 'hiroshima',
           'matsuyama', 'fukuoka')
DEFAULT_INTERVAL = 60


def execute():
    """
    子プロセスを作成してコマンドを実行する。

    子プロセスは自プロセスをプロセスリーダーとした、
    新しいプロセスグループを作成する。

    Return:
    [Int] 実行したコマンドの終了ステータス。

    Exception:
    [RuntimeError] 実行時に何らかのエラーが発生した場合。
    """
    try:
        global logger

        child_pid = os.fork()
        if child_pid == 0:
            # child process
            try:
                # 親プロセスから受け継いだ設定をデフォルトに戻す。
                for sig in (signal.SIGINT, signal.SIGQUIT, signal.SIGTERM):
                    signal.signal(sig, signal.SIG_DFL)

                # 新しいプロセスグループを作成する。
                # このプロセスグループでTimeManagerに登録される。
                os.setpgid(0, 0)
                
                global args
                cmd = u'echo "0:%d:%s" | tm crontab -r %d "%s" | tm set -v - && play_radiru.sh %s %s; tm terminate;' % (args.duration, args.caption.decode('utf-8'), args.duration, args.schedule, args.region, args.channel)
                logger.debug('[CMD] %s' % cmd)

                # 実行する。
                process = subprocess.Popen([cmd.encode('utf-8')], shell=True)
                process.wait()

                os._exit(process.returncode)

            except Exception, e:
                logger.exception(e)
                os._exit(1)
        else:
            # parent process
            logger.info('[SPAWN] pgid:%d' % child_pid)
            
            global child_pgid
            child_pgid = child_pid

            rc = wait_process(child_pid)
            logger.info('[DIED] rc:%d' % rc)            

            return rc

    except Exception, e:
        raise RuntimeError(sys.exc_info()[1]), None, sys.exc_info()[2]


def parse_argument():
    """
    引数を解析する。

    Return:
    [class 'argparse.Namespace'] 解析したコマンドライン

    Exception:
    [RuntimeError] 実行時に何らかのエラーが発生した場合。
    """
    try:
        parser = argparse.ArgumentParser(description=__doc__.encode('utf-8'),
                                 formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument('region', choices=REGIONS, help='地域。')
        parser.add_argument('channel', choices=CHANNELS, help='チャンネル。')
        parser.add_argument('schedule',
                            help='tm crontab形式のスケジュール(ex.0 19 * * *)')
        parser.add_argument('duration', type=int, help='継続時間(sec)')
        parser.add_argument('caption', help='キャプション。')
        parser.add_argument('-i', dest='interval', type=int,
                            default=DEFAULT_INTERVAL,
                            help='実行を繰り返す間隔 (sec)')
        parser.add_argument('-r', dest='repeat', type=int, default=None,
                            help='繰り返す回数 (デフォルトは無制限)')
        parser.add_argument('-v', dest='verbose', action='store_true',
                            help='verboseモード')
        return parser.parse_args()
    except Exception:
        raise RuntimeError(sys.exc_info()[1]), None, sys.exc_info()[2]


def setup_logger():
    """
    loggingをセットアップする。

    Return:
    [class 'logging.Logger'] loggerインスタンス。
    
    Exception:
    [RuntimeError] 実行時に何らかのエラーが発生した場合。
    """
    try:
        global args

        log_fmt = '%(filename)s: %(asctime)s %(levelname)s: %(message)s'
        #log_fmt = '%(filename)s:%(lineno)d: %(asctime)s %(levelname)s: %(message)s'
        
        if args.verbose:
            logging.basicConfig(level=logging.DEBUG, format=log_fmt)
        else:
            logging.basicConfig(format=log_fmt)

        return logging.getLogger(__name__)

    except Exception:
        raise RuntimeError(sys.exc_info()[1]), None, sys.exc_info()[2]


def sig_handler(sig, Handler):
    """
    シグナルハンドラ。
    グローバル変数child_pgidに保存されたプロセスグループに、SIGTERMを送信する。
    送信先のプロセスグループが存在しなくても、エラーは出さない。
    
    Exception:
    [RuntimeError] 実行時に何らかのエラーが発生した場合。
    """
    global child_pgid
    global is_force_termination
    global signo

    is_force_termination = True
    signo = sig

    try:
        os.killpg(child_pgid, sig)
        #logger.debug('send sig %d to pg %d' % (sig, child_pgid))
        
    except OSError, e:
        if e.errno == errno.ESRCH:
            # シグナル送信先プロセスグループが存在しなければ、それでよし。
            #print('Not found, pgid:', child_pgid, file=sys.stderr)
            return
        raise RuntimeError(sys.exc_info()[1]), None, sys.exc_info()[2]

    except Exception, e:
        raise RuntimeError(sys.exc_info()[1]), None, sys.exc_info()[2]


def wait_process(pid):
    """
    プロセス番号がpidのプロセスをwaitして、終了ステータスを返す。

    シグナル割り込みにより終了した場合は、
    シグナル番号+128を終了ステータスとする。

    Arg:
    [Int] waitするプロセスのプロセス番号

    Return:
    [Int] waitしたプロセスの終了ステータス。

    Exception:
    [RuntimeError] 実行時に何らかのエラーが発生した場合。
    """
    while True:
        try:
            (pid, status) = os.waitpid(pid, 0)
                
            # プロセスの終了ステータスを計算する。
            if os.WIFEXITED(status):
                rc = os.WEXITSTATUS(status)
            elif os.WIFSIGNALED(status):
                rc = os.WTERMSIG(status)+128 # signum+128
            else:
                continue

            return rc
        except OSError, e:
            # 割り込まれた場合は、再度waitする。
            if e.errno == errno.EINTR:
                #logger.debug(u'waitpid() EINTR')
                continue
            raise RuntimeError(sys.exc_info()[1]), None, sys.exc_info()[2]
        except Exception, e:
            raise RuntimeError(sys.exc_info()[1]), None, sys.exc_info()[2]


if __name__ == '__main__':

    global args
    global is_force_termination
    global logger
    
    try:
        args = parse_argument()
        logger = setup_logger()

        is_force_termination = False

        for sig in (signal.SIGINT, signal.SIGQUIT, signal.SIGTERM):
            signal.signal(sig,  sig_handler)

        logger.info('[START]')

        while not is_force_termination:

<<<<<<< HEAD
            if execute() != 0:
=======
            if execute() == 1:
>>>>>>> sandbox
                sys.exit(1)

            if is_force_termination:
                break

            if args.repeat != None:
                args.repeat -= 1
                if args.repeat < 0:
                    break

            logger.info('[INTERVAL] %dsec' % args.interval)
            time.sleep(args.interval)

        if is_force_termination:
            global signo
            logger.info('[EXIT] signal %d.' % signo)
            sys.exit(128 + signo)
        else:
            logger.info('[EXIT] OK')
            sys.exit(0)

    except Exception, e:
        logger.exception(e)
        sys.exit(1)
