@echo off
setlocal
powershell -ExecutionPolicy Bypass -File "%~dp0run-agent.ps1" %*
