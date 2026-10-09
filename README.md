# Kumi Reader（Kumi 讀取程式）

Kumi（SS+ 管理系統）的讀取程式：透過雷電模擬器讀取「忍者必須死」的家族成員（暱稱、UID、職位）與深淵排行（暱稱、職位、傷害、挑戰次數），上傳到 Kumi。

## 安裝（給管理員）

1. 到 [Releases](https://github.com/Allen-EO403A/Kumi-Reader/releases/latest) 下載 `Kumi-Reader-Setup-v<版本>.exe` 並執行，照畫面完成安裝。
   - 裝在使用者自己的資料夾（`%LOCALAPPDATA%\Programs\Kumi-Reader`），不需要系統管理員；缺少 .NET 10 Desktop Runtime 時會一併安裝（這一步會跳出 Windows 的權限確認）。
   - 出新版時直接執行新的安裝程式即可，金鑰與本機結果會保留。
2. 雷電模擬器解析度設為 1920×1080。
3. 從開始選單或桌面的「Kumi 讀取程式」開啟。

## 使用流程

1. **設定金鑰**（第一次或換金鑰時）：在網站「讀取程式金鑰」頁產生金鑰並按「複製」→ 開啟「Kumi 讀取程式」，選擇模擬器 → 勾選「設定金鑰（從剪貼簿）」，第一次請在選項填後端網址 → 開始。金鑰會寫進本機設定並清除剪貼簿，不會出現在紀錄檔。
2. **讀取家族成員**（隨時）：遊戲中打開家族面板的「成員」分頁 → 勾選「讀取家族成員」→ 開始。讀到底時核對人數；人數不符時，停在「成員」分頁執行「補讀缺少的成員」，程式會從最上面一路滑到底，只讀還沒讀過的人。
3. **讀取深淵排行**（週五 21:00 深淵結束後、下一個週五 20:00 排行清空前）：打開深淵排行榜的「家族狀況」分頁 → 勾選「讀取深淵排行」→ 開始。
4. **上傳讀取結果**：讀取任務只把結果存在本機，執行「上傳讀取結果」才會上傳（家族成員與深淵排行一起）。上傳後到網站「深淵審核」確認深淵排行。

一把讀取程式金鑰最多綁定一份程式的家族成員讀取與深淵排行讀取（第一次使用時綁定）。要換電腦，或刪除程式資料夾後重新安裝，請在網站作廢金鑰並產生新的（用安裝程式更新版本不受影響）。

## 開發

```bash
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python tools\download_ocr_model.py
.venv\Scripts\python -m pytest
.venv\Scripts\python tools\build_installer.py <版本>   # 產生 dist\release\Kumi-Reader-Setup-v<版本>.exe（需要 Inno Setup 6）
```

## 授權

Copyright (C) 2026 Allen <allen@umail.tw>

本程式是自由軟體：你可以依自由軟體基金會發布的 GNU 通用公眾授權條款（GPL）第 3 版，或（依你的選擇）任何更新的版本，重新散布和／或修改本程式。散布本程式是希望它有用，但**沒有任何擔保**，甚至沒有適售性或特定目的適用性的隱含擔保。詳見 [LICENSE](LICENSE)（GPL-3.0 全文）。

安裝程式內附的第三方元件（MFAAvalonia、MaaFramework、OCR 模型、Python 等）依各自的授權發布，見 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
