# kumi-reader

Kumi（SS+ 管理系統）的讀取程式：透過雷電模擬器讀取「忍者必須死3」的家族成員（暱稱、UID、職位）與深淵排行（暱稱、職位、傷害、挑戰次數），上傳到 Kumi。

## 安裝（給管理員）

1. 先安裝 [.NET 10 Desktop Runtime（x64）](https://dotnet.microsoft.com/download/dotnet/10.0)（MFAAvalonia 介面需要）。
2. 解壓縮 `kumi-reader-v<版本>.zip` 到任一資料夾（路徑避免太深）。
3. 雷電模擬器解析度設為 1920×1080。

## 使用流程

1. **設定金鑰**（第一次或換金鑰時）：在網站「讀取程式金鑰」頁產生金鑰並按「複製」→ 執行 `MFAAvalonia.exe`，選擇模擬器 → 勾選「設定金鑰（從剪貼簿）」，第一次請在選項填後端網址 → 開始。金鑰會寫進本機設定並清除剪貼簿，不會出現在紀錄檔。
2. **讀取家族成員**（隨時）：遊戲中打開家族面板的「成員」分頁 → 勾選「讀取家族成員」→ 開始。讀到底時核對人數；人數不符時，把名單移到缺少成員那一頁，再執行「補讀目前畫面」。
3. **讀取深淵排行**（週五 21:00 深淵結束後、排行清空前）：打開深淵排行榜的「家族狀況」分頁 → 勾選「讀取深淵排行」→ 開始。上傳後到網站「深淵審核」確認。

一把讀取程式金鑰最多綁定一份程式的家族成員讀取與深淵排行讀取（第一次使用時綁定）。要換電腦或重新安裝，請在網站作廢金鑰並產生新的。

## 開發

```bash
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python tools\download_ocr_model.py
.venv\Scripts\python -m pytest
.venv\Scripts\python tools\build_package.py <版本>
```
