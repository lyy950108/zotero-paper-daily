# 🔬 Zotero-Paper-Daily (Extended)

> 基于 [TideDra/zotero-arxiv-daily](https://github.com/TideDra/zotero-arxiv-daily) 扩展，**新增 PubMed、bioRxiv、medRxiv** 数据源支持，特别适合**生物医学/皮肤科**研究者。

## ✨ 新增功能

在原项目基础上增加：

- **PubMed** 数据源：支持 MeSH 词检索，覆盖所有已发表的医学文献
- **bioRxiv** 数据源：支持按类别和关键词过滤预印本
- **medRxiv** 数据源：临床/公共卫生预印本
- **来源标签**：邮件中每篇论文标注来源（arXiv / PubMed / bioRxiv / medRxiv）
- **多来源融合排序**：所有来源的论文统一用 Zotero 库进行兴趣匹配
- **皮肤科预配置模板**：开箱即用

---

## 🚀 快速开始（皮肤科配置）

### 1. Fork 本仓库

### 2. 配置 GitHub Secrets

进入仓库 → `Settings` → `Secrets and variables` → `Actions` → `New repository secret`

#### 必填项

| Key | Value | 说明 |
|-----|-------|------|
| `ZOTERO_ID` | `12345678` | [获取 Zotero ID](https://www.zotero.org/settings/security) |
| `ZOTERO_KEY` | `AB5tZ877...` | 同上页面创建 API Key |
| `SMTP_SERVER` | `smtp.163.com` | 163邮箱 SMTP 服务器 |
| `SMTP_PORT` | `465` | SSL 端口 |
| `SENDER` | `xxx@163.com` | 你的 163 邮箱 |
| `SENDER_PASSWORD` | `授权码` | 163邮箱 SMTP 授权码（非登录密码） |
| `RECEIVER` | `xxx@xxx.com` | 接收推荐的邮箱 |

#### PubMed 配置（皮肤科推荐）

| Key | Value | 说明 |
|-----|-------|------|
| `PUBMED_QUERY` | 见下方 | PubMed 搜索语句 |
| `NCBI_API_KEY` | （可选） | [申请 NCBI API Key](https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/) 提高速率 |

**皮肤科 PubMed 搜索语句示例：**

```
("skin diseases"[MeSH] OR "dermatology"[MeSH] OR "psoriasis"[MeSH] OR "dermatitis, atopic"[MeSH] OR "melanoma"[MeSH] OR "skin neoplasms"[MeSH] OR "wound healing"[MeSH] OR "epidermis"[MeSH] OR "skin"[MeSH]) AND (hasabstract[text])
```

你可以根据自己的研究方向精简，比如只关注特应性皮炎：
```
("dermatitis, atopic"[MeSH] OR "atopic eczema" OR "skin barrier") AND (hasabstract[text])
```

#### bioRxiv 配置

| Key | Value | 说明 |
|-----|-------|------|
| `BIORXIV_CATEGORIES` | `cell_biology+immunology+molecular_biology` | 用 `+` 分隔类别 |
| `BIORXIV_KEYWORDS` | `skin+dermatitis+epiderm+keratinocyte+melanocyte+wound+psoriasis` | 用 `+` 分隔关键词 |

#### medRxiv 配置

| Key | Value | 说明 |
|-----|-------|------|
| `MEDRXIV_KEYWORDS` | `skin+dermatology+atopic+psoriasis+melanoma+eczema` | 临床相关关键词 |

#### arXiv 配置（AI 辅助诊断方向）

| Key | Value | 说明 |
|-----|-------|------|
| `ARXIV_QUERY` | `cs.CV+eess.IV+cs.LG` | 计算机视觉/医学图像 |

#### LLM 配置

| Key | Value | 说明 |
|-----|-------|------|
| `USE_LLM_API` | `1` | 使用 API（推荐）|
| `OPENAI_API_KEY` | `sk-xxx` | API Key |
| `OPENAI_API_BASE` | `https://api.siliconflow.cn/v1` | SiliconFlow（免费）或 OpenAI |
| `MODEL_NAME` | `Qwen/Qwen2.5-7B-Instruct` | 模型名 |

#### 其他配置

| Key | Value | 说明 |
|-----|-------|------|
| `MAX_PAPER_NUM` | `30` | 每日最多推荐论文数 |
| `FETCH_DAYS` | `1` | 回溯天数（默认 1） |
| `SEND_EMPTY` | `False` | 无新论文时是否发送空邮件 |

### 3. 配置 Repository Variables

进入 `Settings` → `Secrets and variables` → `Actions` → `Variables`

| Key | Value |
|-----|-------|
| `LANGUAGE` | `Chinese` |
| `ZOTERO_IGNORE` | （可选）忽略的 Zotero 文件夹 |

### 4. 测试运行

进入 `Actions` → `Send-papers-daily` → `Run workflow`

---

## 📁 新增文件说明

```
├── biomed_paper.py              # BiomedPaper 类（兼容 ArxivPaper 接口）
├── biomed_fetcher.py            # PubMed/bioRxiv/medRxiv API 数据获取
├── main_extended.py             # 扩展版主程序（替换原 main.py）
├── construct_email_extended.py  # 扩展版邮件构建（支持多来源）
├── .github/workflows/main.yml  # GitHub Actions 工作流
│
│ 以下为原项目文件（保持不变）：
├── paper.py                     # ArxivPaper 类
├── recommender.py               # 推荐引擎（embedding 相似度）
├── llm.py                       # LLM 集成
├── construct_email.py           # 原版邮件构建
└── main.py                      # 原版主程序
```

---

## 📖 工作原理

```
┌─────────────────────────────────────────────────────────────┐
│                    你的 Zotero 文献库                         │
│              （代表你的研究兴趣画像）                          │
└──────────────────────┬──────────────────────────────────────┘
                       │ embedding
                       ▼
┌──────────┬──────────┬──────────┬──────────┐
│  arXiv   │ PubMed   │ bioRxiv  │ medRxiv  │  ← 每日新论文
└────┬─────┴────┬─────┴────┬─────┴────┬─────┘
     │          │          │          │
     └──────────┴──────────┴──────────┘
                       │
                       ▼
              相似度排序 + LLM 生成 TL;DR
                       │
                       ▼
                 📮 发送邮件到你的邮箱
```

---

## 🔧 皮肤科常用 PubMed MeSH 词参考

| 研究方向 | 推荐 MeSH 词 |
|---------|-------------|
| 特应性皮炎 | `"dermatitis, atopic"[MeSH]` |
| 银屑病 | `"psoriasis"[MeSH]` |
| 黑色素瘤 | `"melanoma"[MeSH]` |
| 皮肤肿瘤 | `"skin neoplasms"[MeSH]` |
| 伤口愈合 | `"wound healing"[MeSH]` |
| 皮肤屏障 | `"epidermis"[MeSH] OR "skin barrier"` |
| 皮肤免疫 | `"skin"[MeSH] AND "immunity"[MeSH]` |
| 毛囊/脱发 | `"hair follicle"[MeSH] OR "alopecia"[MeSH]` |
| 皮肤微生物组 | `"microbiota"[MeSH] AND "skin"[MeSH]` |
| AI 皮肤诊断 | `"dermoscopy"[MeSH] AND "deep learning"` |
| 皮肤干细胞 | `"stem cells"[MeSH] AND "skin"[MeSH]` |
| 光疗 | `"phototherapy"[MeSH] AND "skin diseases"[MeSH]` |

可在 [PubMed MeSH Browser](https://meshb.nlm.nih.gov/) 查找更多词条。

---

## bioRxiv 可用类别

适合皮肤科基础研究的 bioRxiv 类别：

- `cell_biology` - 细胞生物学
- `immunology` - 免疫学
- `molecular_biology` - 分子生物学
- `developmental_biology` - 发育生物学
- `cancer_biology` - 肿瘤生物学
- `genomics` - 基因组学
- `bioinformatics` - 生物信息学
- `microbiology` - 微生物学
- `pharmacology_and_toxicology` - 药理与毒理
- `pathology` - 病理学
- `systems_biology` - 系统生物学

用 `+` 连接多个类别，如：`cell_biology+immunology+cancer_biology`

---

## ❓ FAQ

**Q: 原来的 arXiv 功能还能用吗？**
A: 完全兼容。设了 `ARXIV_QUERY` 就会同时检索 arXiv，不设则跳过。

**Q: 可以只用 PubMed 不用 arXiv 吗？**
A: 可以。只设 `PUBMED_QUERY`，不设 `ARXIV_QUERY` 即可。

**Q: 每天会消耗多少 GitHub Actions 时间？**
A: 取决于 `MAX_PAPER_NUM`。PubMed/bioRxiv 获取很快，主要时间花在 LLM 生成 TL;DR。使用 API（`USE_LLM_API=1`）通常 5-15 分钟。

**Q: NCBI API Key 必须吗？**
A: 不必须，但推荐申请。没有 Key 限制 3 次/秒，有 Key 提升到 10 次/秒。

---

## 🙏 致谢

- [TideDra/zotero-arxiv-daily](https://github.com/TideDra/zotero-arxiv-daily) - 原始项目
- [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/) - PubMed API
- [bioRxiv API](https://api.biorxiv.org/) - bioRxiv/medRxiv API
