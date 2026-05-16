# 数学建模竞赛总调度智能体

基于大语言模型的双 Agent 协同系统，自动完成数学建模竞赛全流程：从赛题分析、论文框架搭建、数学公式推导，到代码生成与求解输出。

## 架构设计

```
用户上传赛题 → Agent1(题目分析与论文建模) → Agent2(模型算法与代码生成) → 打包下载
```

- **Agent1 — 题目分析与论文建模Agent**：负责赛题深度解读、解题逻辑梳理、论文框架搭建、学术化文字撰写、完整数学公式推导与模型论证
- **Agent2 — 最优模型算法与代码生成Agent**：负责模型优选、算法设计、Python 代码编写、数据处理、求解运算、结果可视化与保存

## 快速开始

### 1. 环境准备

```bash
# 克隆仓库
git clone https://github.com/YOUR_USERNAME/jmandcode.git
cd jmandcode

# 创建虚拟环境（推荐）
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入你的 DeepSeek API Key
DEEPSEEK_API_KEY=sk-your-api-key-here
DEEPSEEK_MODEL=deepseek-v4-pro   # 默认，可更改为其他模型
```

### 3. 启动服务

```bash
python app.py
```

访问 http://localhost:5000

## 使用方法

### 基本流程

1. **上传赛题文件**：支持 PDF、DOCX、TXT、MD 格式
2. **上传附件数据**（可选）：支持 Excel、CSV、JSON 等数据文件
3. **点击启动**：双 Agent 自动协同分析
4. **查看结果**：分析文档（论文级）+ 各问题求解代码
5. **下载成果**：打包下载全套 ZIP 文件

### 训练知识库（可选）

上传往年优秀论文、论文框架模板、参考代码，让 Agent1 模仿其风格与深度：

- **论文框架**：`论文框架模板.md` → Agent1 会按此结构输出
- **优秀论文**：可添加往年国赛一等奖 PDF → Agent1 会模仿写作风格与推导深度
- **参考代码**：规范 Python 代码 `.py` → Agent2 会模仿代码风格

数据存储在 `training/` 目录下，首次读取后缓存，文件不变不重复读取。

## 项目结构

```
jmandcode/
├── app.py                    # Flask Web 主入口
├── agents/
│   ├── analysis_agent.py     # Agent1：题目分析与建模
│   ├── code_agent.py         # Agent2：算法与代码生成
│   └── orchestrator.py       # 总调度器
├── utils/
│   ├── file_handler.py       # 文件上传/解析
│   └── knowledge_base.py     # 知识库引擎
├── templates/
│   └── index.html            # 前端页面
├── static/
│   ├── css/style.css         # 样式
│   └── js/main.js            # 前端交互 & SSE
├── training/                 # 训练知识库目录
│   ├── frameworks/           #   论文框架模板
│   ├── papers/               #   优秀论文
│   └── codes/                #   参考代码
├── requirements.txt
├── .env.example              # 环境变量模板
└── .gitignore
```

## 技术栈

- **后端**：Flask + SSE 实时进度推送
- **AI 模型**：DeepSeek API（OpenAI 兼容）
  - Agent1：`deepseek-v4-pro`（推理模型）
  - Agent2：`deepseek-v4-pro`（可用 .env 配置）
- **文件处理**：PyPDF2、python-docx、pandas

## 特性

- 📄 支持 PDF/DOCX/TXT/MD 赛题文件上传
- 📊 支持 Excel/CSV/JSON 多个附件数据同传
- 🔄 SSE 实时进度推送 + 断线自动轮询兜底
- 📐 LaTeX 数学公式规范输出（行内/独立公式自动区分编号）
- 📦 分问题独立代码文件，每个 `.py` 可直接运行
- 🎓 知识库注入，模仿优秀论文风格与深度
- 💾 训练数据缓存，避免重复读取

## License

MIT
