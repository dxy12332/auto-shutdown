@echo off
rem 用 pythonw.exe 启动，避免闪出黑色控制台窗口。
rem 若把 Python 装到了别处或未加入 PATH，把下面的路径改成你的 pythonw.exe 绝对路径。
cd /d "%~dp0"
start "" "C:\Users\ch\AppData\Local\Programs\Python\Python312\pythonw.exe" "%~dp0main.py"
