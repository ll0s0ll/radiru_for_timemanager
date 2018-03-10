NHKラジオの聴取をTimeManagerにスケジュールするためのプログラムです。

標準では繰り返し実行されます。繰り返す回数、間隔はオプションで設定できます。

EXAMPLE
```
# NHKラジオ第一 仙台放送局のすっぴんをスケジュールする。
$ ./radiru_for_timemanager.py sendai r1 "5 8 * * 1-5" 13500 "すっぴん"
```

内部で以下のプログラムを呼び出しています。
- [play_radiru.sh](https://github.com/ll0s0ll/play_radiru)
- [TimeManager](https://github.com/ll0s0ll/TimeManager)