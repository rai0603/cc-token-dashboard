# py2app 進入點：被打包成 .app 後，雙擊即以選單列模式啟動
import cc_token_dashboard as m

if __name__ == "__main__":
    m.run_menubar(8787, 3)
