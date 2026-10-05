# kumi-reader-members

Kumi（SS+ 管理系統）的家族成員讀取程式：透過雷電模擬器讀取「忍者必須死3」家族成員的暱稱、UID 與職位，上傳到 Kumi。

## 安裝（給管理員）

1. 先安裝 [.NET 10 Desktop Runtime（x64）](https://dotnet.microsoft.com/download/dotnet/10.0)（MFAAvalonia 介面需要）。
2. 解壓縮 `kumi-reader-members-v<版本>.zip` 到任一資料夾（路徑避免太深）。
3. 把資料夾內的 `.env.example` 複製成 `.env`，填入後端網址與讀取程式金鑰。
4. 執行 `MFAAvalonia.exe`，選擇雷電模擬器，勾選「讀取家族成員」後開始。

## 使用前準備

1. 雷電模擬器解析度設為 1920×1080，並關閉按鍵提示。
2. 把 `.env.example` 複製成 `.env`，填入後端網址與網站產生的讀取程式金鑰。
3. 遊戲中打開家族面板的「成員」分頁，再從 MFAAvalonia 執行「讀取家族成員」。

一把讀取程式金鑰只能綁定一份家族成員讀取程式（第一次使用時綁定）。要換電腦或重新安裝，請在網站作廢金鑰並產生新的。

## 開發

```bash
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python tools\download_ocr_model.py
.venv\Scripts\python -m pytest
```
