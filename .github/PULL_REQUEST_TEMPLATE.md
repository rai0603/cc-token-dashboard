<!-- 標題建議：fix: … / feat: … / docs: … / Title: fix: … / feat: … -->

## 改了什麼 / What
<!-- 一兩句說明這個 PR 做了什麼 / One or two lines on what this PR does -->

## 為什麼 / Why
<!-- 解決的問題或動機 / The problem or motivation. 連結 issue：Closes #N -->

## 怎麼驗證 / How verified
- [ ] `make test` 全綠 / green
- [ ] 若改打包：實跑 `make app` 確認 `.app` 能開 / if packaging changed, ran `make app` and the `.app` opens
- [ ] 其他 / other:

## 檢查清單 / Checklist
- [ ] `status` / `serve` 仍維持純標準函式庫 / kept stdlib-only
- [ ] 收集器仍快且不拋例外到 stdout / collector stays fast and never raises
- [ ] 範圍聚焦，沒有 scope 外的順手重構 / focused scope, no drive-by refactors
