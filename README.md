# finpress · 每日财经简报自动生成

## 使用顺序
1. （已完成）把本仓库所有文件上传到 GitHub
2. 存 Secret：Settings → Secrets and variables → Actions → New repository secret
   - Name: MOONSHOT_API_KEY
   - Value: 你的 Moonshot API Key（sk- 开头）
3. 手动验证：顶部 Actions → 左侧 daily-finpress → 右侧 Run workflow → 绿色按钮
4. 等约 2 分钟，点进运行记录，页面底部 Artifacts 里下载 article（内含生成的 .md 文章）

## 常见问题
- 运行记录显示 401：Key 错误、Secret 名字拼错、或 Moonshot 账户余额为 0
- 文章里没有行情数字：多为周末休市或 akshare 接口变动，看运行日志里 fetch_data.py 的 notes
- 想自动推送企业微信/邮件：在 generate.py 后加一步调用 webhook 即可
