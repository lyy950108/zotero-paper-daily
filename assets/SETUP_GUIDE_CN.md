# 🩺 皮肤科研究者 - 10分钟快速部署指南

## 第一步：Fork 原始仓库

1. 打开 https://github.com/TideDra/zotero-arxiv-daily
2. 点击右上角 **Fork** 按钮
3. Fork 到你自己的 GitHub 账号下

## 第二步：添加扩展文件

在你 Fork 的仓库中，添加以下 4 个新文件（点击 `Add file` → `Create new file`）：

| 文件名 | 内容来源 |
|--------|---------|
| `biomed_paper.py` | 复制本项目中的 biomed_paper.py |
| `biomed_fetcher.py` | 复制本项目中的 biomed_fetcher.py |
| `main_extended.py` | 复制本项目中的 main_extended.py |
| `construct_email_extended.py` | 复制本项目中的 construct_email_extended.py |

## 第三步：修改 GitHub Actions 工作流

编辑 `.github/workflows/main.yml`，将运行命令改为：

```yaml
- name: Run paper recommendation
  run: python main_extended.py
```

或者直接用本项目的 `.github/workflows/main.yml` 替换。

## 第四步：配置 Secrets

进入你的仓库 → `Settings` → `Secrets and variables` → `Actions`

### 必填 Secrets（逐条添加）：

```
ZOTERO_ID          → 你的 Zotero 数字 ID
ZOTERO_KEY         → 你的 Zotero API Key
SMTP_SERVER        → smtp.163.com
SMTP_PORT          → 465
SENDER             → 你的邮箱@163.com
SENDER_PASSWORD    → 163邮箱 SMTP 授权码
RECEIVER           → 接收邮件的邮箱
```

### PubMed Secret（核心！）：

```
PUBMED_QUERY → ("skin diseases"[MeSH] OR "dermatology"[MeSH]) AND (hasabstract[text])
```

### bioRxiv Secrets：

```
BIORXIV_CATEGORIES → cell_biology+immunology+molecular_biology
BIORXIV_KEYWORDS   → skin+epiderm+keratinocyte+dermatitis+psoriasis+wound
```

### medRxiv Secret：

```
MEDRXIV_KEYWORDS → skin+dermatology+atopic+psoriasis+melanoma+eczema
```

### LLM Secrets（用于生成 TL;DR）：

```
USE_LLM_API    → 1
OPENAI_API_BASE → https://api.siliconflow.cn/v1
OPENAI_API_KEY  → 你的 SiliconFlow API Key（免费注册）
MODEL_NAME      → Qwen/Qwen2.5-7B-Instruct
```

### 其他 Secrets：

```
MAX_PAPER_NUM → 30
FETCH_DAYS    → 1
```

## 第五步：配置 Variables

进入 `Settings` → `Secrets and variables` → `Actions` → `Variables` 标签页

```
LANGUAGE → Chinese
```

## 第六步：测试

1. 进入仓库 `Actions` 页面
2. 选择 `Send-papers-daily`
3. 点击 `Run workflow`
4. 等待完成，检查你的邮箱

## 常见问题

**邮件发送失败？**
- 确认 163 邮箱已开启 SMTP 服务
- 确认 SENDER_PASSWORD 是授权码不是登录密码
- 试试 SMTP_PORT 用 994

**没有找到论文？**
- 检查 PUBMED_QUERY 语法是否正确
- 可以先在 https://pubmed.ncbi.nlm.nih.gov/ 手动测试查询语句
- 如果是周末/节假日，arXiv 可能没有新论文（PubMed 通常每天都有）

**想调整推荐的精准度？**
- 优化 Zotero 库：多添加你核心方向的论文
- 精简 PUBMED_QUERY：缩小到你最关注的 2-3 个 MeSH 词
- 调整 MAX_PAPER_NUM：减少数量提高质量
