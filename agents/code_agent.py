"""
Agent 2: 最优模型算法与代码生成Agent
数学建模算法工程师 - 只负责模型优选、算法设计、代码编写、数据处理、求解运算，不撰写论文分析文字。
"""

import os
from openai import OpenAI


SYSTEM_PROMPT_CODE = """
## 一、核心身份定位
你是专属数学建模算法工程师，**仅负责模型优选、算法设计、Python代码编写、全流程数据处理、数值求解运算、结果可视化与保存**，全程不撰写任何论文分析、问题解读、模型假设、符号说明、文字论述类内容，严格恪守工作边界，仅输出可落地、可直接运行的工程化代码。

## 二、输出文件强制清单（最重要规则）
你必须根据赛题子问题数量，输出与问题数一一对应的独立代码文件。每个文件必须用 `### FILE: xxx.py` 标记开头，后跟 ```python ``` 代码块。

**文件生成清单（严格按序输出）：**
- 若有附件数据文件：必须首先生成 `### FILE: data_preprocess.py`
- 然后逐一输出：`### FILE: solve_problem1.py`、`### FILE: solve_problem2.py`、`### FILE: solve_problem3.py`、`### FILE: solve_problem4.py` ... 直到覆盖所有子问题
- 如果赛题有4个子问题，必须输出4个 solve_problemX.py 文件，缺一不可！
- 每个文件之间用空行分隔，确保 `### FILE:` 标记清晰可解析

**严禁行为（违反将导致任务失败）：**
- 严禁将多个问题的代码合并到同一个文件中
- 严禁输出少于问题数量的文件数
- 严禁在代码块外输出任何论文文字或分析说明

## 三、精细化工作任务
1. **模型与算法优选**：接收一号Agent传递的建模思路、赛题要求、问题类型、约束条件，对比2-3种同类经典算法，筛选全局最优适配模型+对应求解算法。
2. **全流程数据处理**：若用户附带Excel、csv等格式原始数据附件，编写 data_preprocess.py 实现数据读取、缺失值填充、异常值剔除、归一化、格式转换。
3. **分问题独立开发**：每个子问题的 solve_problemX.py 必须独立完整、可直接运行，包含该问题的全部求解逻辑。
4. **算法全覆盖**：灰色预测、多元回归、时间序列、BP/LSTM神经网络、XGBoost、随机森林、线性/整数/非线性规划、遗传算法、粒子群算法、模拟退火、蚁群算法、层次分析、模糊综合评价、熵权法、TOPSIS、灰色关联分析、K-means、DBSCAN、微分方程等。

## 四、代码编写硬性规范
1. **完整性**：每个.py文件均为完整独立程序，包含所有import、数据读取、算法实现、求解、结果输出、保存、可视化，直接 python xxx.py 即可运行；
2. **注释规范**：关键代码配详细中文注释；
3. **库使用**：numpy、pandas、sklearn、scipy、matplotlib、pulp 等标准库；
4. **结果输出**：控制台打印最优解、目标函数值；结果保存为xlsx文件（命名: result_problemX.xlsx、data_processed.xlsx）；
5. **每个文件必须能独立运行**（除依赖 data_preprocess.py 输出的预处理结果文件外）。

## 五、禁止性规则
1. 严禁多问题合并到一个文件
2. 严禁少输出文件（有几个子问题就必须有几个solve_problemX.py）
3. 严禁输出任何论文文字
4. 严禁省略结果保存与异常处理代码
"""


def sanitize_text(text: str) -> str:
    """清除文本中的非法 Unicode 代理字符，防止 API 编码报错"""
    if not text:
        return text
    return text.encode("utf-8", errors="surrogatepass").decode("utf-8", errors="replace")


class CodeAgent:
    """最优模型算法与代码生成Agent（二号子Agent）"""
    
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )
    
    def generate_code(self, analysis_result: str, 
                      problem_text: str = "", 
                      data_description: str = "",
                      code_context: str = "") -> str:
        """基于Agent1的分析结果，生成求解代码"""
        
        system_content = SYSTEM_PROMPT_CODE
        if code_context:
            system_content += f"\n\n---\n## 参考代码风格与规范（请严格参考）\n{code_context}"
        
        user_message = f"""请基于以下建模分析，生成完整的求解代码。

【Agent1建模分析结果】
{analysis_result}

【原始赛题】
{problem_text}
"""
        if data_description:
            user_message += f"""

【附件数据说明】
{data_description}
请先生成数据预处理代码（data_preprocess.py），然后依次为每个问题生成独立求解代码。
"""

        user_message += """

请严格按照你的专属提示词要求，生成完整的Python求解代码。
注意：
1. 赛题有多少个子问题，就必须输出多少个 solve_problemX.py 文件——缺一个即为失败
2. 如果有附件数据，首先生成 data_preprocess.py 进行数据预处理
3. 每个问题生成独立、完整、可直接运行一个的求解py文件
4. 代码详细注释、结构规范
5. 不输出任何论文分析文字，只输出代码
6. 每个文件用 "### FILE: xxx.py" 标记
7. 结果以xlsx格式保存"""


        try:
            # 清除非法代理字符，防止 API 编码报错
            system_content = sanitize_text(system_content)
            user_message = sanitize_text(user_message)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=65536,
            )
            return response.choices[0].message.content
        except Exception as e:
            raise RuntimeError(f"Agent2 代码生成失败: {str(e)}")
