"""
总调度器 - Master Orchestrator
协调两大子Agent，串联完整数模流程
Agent1(分析建模) → Agent2(算法代码) → 汇总输出
"""

import os
import re
import json
import zipfile
import tempfile
from datetime import datetime
from .analysis_agent import AnalysisAgent
from .code_agent import CodeAgent


class Orchestrator:
    """总调度器：全程协同两大子Agent完成数模全流程"""
    
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
        
        self.agent1 = AnalysisAgent(
            api_key=self.api_key, 
            base_url=self.base_url, 
            model=self.model
        )
        self.agent2 = CodeAgent(
            api_key=self.api_key, 
            base_url=self.base_url, 
            model=self.model
        )
        self.kb = None  # 懒加载，避免循环导入
    
    def run(self, problem_text: str, data_description: str = "",
            progress_callback=None) -> dict:
        """
        执行完整数模调度流程
        
        Args:
            problem_text: 赛题文本
            data_description: 附件数据说明
            progress_callback: 进度回调函数，接收 (stage, message)
        
        Returns:
            dict: {
                'analysis_doc': str,       # Agent1 分析文档(Markdown)
                'code_files': dict,        # {filename: code_content}
                'output_dir': str,         # 输出目录路径
                'zip_path': str,           # 打包后的zip路径
            }
        """
        results = {}
        
        # 构建知识库上下文
        if self.kb is None:
            from utils.knowledge_base import KnowledgeBase
            self.kb = KnowledgeBase()
        kb_stats = self.kb.get_all_stats()
        paper_context = self.kb.build_paper_context(max_chars_per_file=20000) if kb_stats["frameworks"] + kb_stats["papers"] > 0 else ""
        code_context = self.kb.build_code_context() if kb_stats["codes"] > 0 else ""
        
        # 阶段一：Agent1 题目分析与建模
        if progress_callback:
            progress_callback("analysis", f"Agent1 正在分析赛题（知识库: {kb_stats['frameworks']}框架/{kb_stats['papers']}论文）...")
        
        try:
            analysis_doc = self.agent1.analyze(problem_text, data_description, paper_context=paper_context)
            results['analysis_doc'] = analysis_doc
        except Exception as e:
            if progress_callback:
                progress_callback("error", f"Agent1 分析失败: {str(e)}")
            raise
        
        # 从 Agent1 分析文档末尾提取子问题总数
        problem_count = self._extract_problem_count(analysis_doc)
        
        if progress_callback:
            progress_callback("analysis_done", f"Agent1 分析完成（检测到 {problem_count} 个子问题），即将启动Agent2生成代码...")
        
        # 阶段二：Agent2 代码生成
        if progress_callback:
            progress_callback("code_gen", f"Agent2 正在为 {problem_count} 个子问题生成求解代码...")
        
        code_files = {}
        for attempt in range(3):
            try:
                code_output = self.agent2.generate_code(
                    analysis_result=analysis_doc,
                    problem_text=problem_text,
                    data_description=data_description,
                    code_context=code_context
                )
                code_files = self._parse_code_files(code_output)
                
                solve_files = [k for k in code_files if k.startswith("solve_problem")]
                
                if len(solve_files) >= problem_count:
                    break
                
                if attempt < 2:
                    if progress_callback:
                        progress_callback("code_gen", f"Agent2 输出文件不足（{len(solve_files)}/{problem_count}），正在重试第{attempt+2}次...")
            except Exception as e:
                if attempt == 2:
                    if progress_callback:
                        progress_callback("error", f"Agent2 代码生成失败: {str(e)}")
                    raise
        
        results['code_files'] = code_files
        
        if progress_callback:
            progress_callback("code_done", "Agent2 代码生成完成，正在打包输出文件...")
        
        # 阶段三：汇总输出
        output_dir = self._save_outputs(results, problem_text)
        results['output_dir'] = output_dir
        
        if progress_callback:
            progress_callback("packaging", f"输出文件已保存至 {output_dir}，正在打包...")
        
        zip_path = self._create_zip(output_dir)
        results['zip_path'] = zip_path
        
        if progress_callback:
            progress_callback("done", "全流程完成！点击下载获取全套成果文件。")
        
        return results
    
    def _extract_problem_count(self, analysis_doc: str) -> int:
        """从Agent1的分析文档末尾提取子问题总数，默认4"""
        import re
        # 匹配 "子问题总数：4" 或 "子问题总数: 4" 或 "问题总数：4" 等
        pattern = r'(?:子问题|问题)\s*总数\s*[:：]\s*(\d+)'
        matches = re.findall(pattern, analysis_doc)
        if matches:
            return int(matches[-1])
        # 备选：统计 "问题一" "问题二" 等标题
        sub_pattern = r'###\s*\d+\.\d+\s*问题[一二三四五六七八九十\d]+'
        count = len(re.findall(sub_pattern, analysis_doc))
        if count > 0:
            return count
        # 再备选：统计 "### 4.X" 小节
        section_count = len(re.findall(r'###\s*\d+\.\d+\s', analysis_doc))
        return max(section_count, 4)

    def _parse_code_files(self, code_output: str) -> dict:
        """解析Agent2输出，提取各个独立.py文件"""
        code_files = {}
        
        pattern = r'###\s*FILE:\s*(\S+\.py)\s*\n```python\s*\n(.*?)```'
        matches = re.findall(pattern, code_output, re.DOTALL)
        
        for filename, code in matches:
            clean_code = code.strip()
            code_files[filename] = clean_code
        
        if not code_files:
            alt_pattern = r'```python\s*\n(.*?)```'
            alt_matches = re.findall(alt_pattern, code_output, re.DOTALL)
            if alt_matches:
                for i, code in enumerate(alt_matches):
                    code_files[f"solution_part{i+1}.py"] = code.strip()
        
        if not code_files:
            code_files["solution.py"] = code_output
        
        return code_files
    
    def _save_outputs(self, results: dict, problem_text: str) -> str:
        """保存所有输出文件到本地目录"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "outputs",
            f"mcm_solution_{timestamp}"
        )
        os.makedirs(output_dir, exist_ok=True)
        
        with open(os.path.join(output_dir, "problem_analysis.md"), "w", encoding="utf-8") as f:
            f.write(results.get('analysis_doc', ''))
        
        with open(os.path.join(output_dir, "original_problem.txt"), "w", encoding="utf-8") as f:
            f.write(problem_text)
        
        for filename, code in results.get('code_files', {}).items():
            filepath = os.path.join(output_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(code)
        
        summary = {
            "生成时间": timestamp,
            "包含文件": ["problem_analysis.md", "original_problem.txt"] 
                       + list(results.get('code_files', {}).keys()),
            "Agent1分析文档": "problem_analysis.md",
            "Agent2代码文件": list(results.get('code_files', {}).keys()),
        }
        with open(os.path.join(output_dir, "output_summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        return output_dir
    
    def _create_zip(self, output_dir: str) -> str:
        """将输出目录打包为zip"""
        zip_path = output_dir + ".zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, os.path.dirname(output_dir))
                    zf.write(file_path, arcname)
        return zip_path
