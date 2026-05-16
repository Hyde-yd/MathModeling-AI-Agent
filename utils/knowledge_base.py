"""
知识库引擎
自动读取训练数据目录中的论文框架、优秀论文、参考代码
并构建注入到Agent提示词中的上下文
"""

import os
import re
from datetime import datetime


class KnowledgeBase:
    """
    训练知识库管理器
    扫描 training/ 目录，将参考论文和代码注入到Agent提示词中
    
    目录结构:
      training/
        frameworks/   ← 论文框架模板 (.md / .txt)
        papers/       ← 往年优秀论文 (.md / .txt / .pdf)
        codes/        ← 参考求解代码 (.py)
    """
    
    def __init__(self, base_dir: str = None):
        if base_dir is None:
            base_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "training"
            )
        self.base_dir = base_dir
        self.frameworks_dir = os.path.join(base_dir, "frameworks")
        self.papers_dir = os.path.join(base_dir, "papers")
        self.codes_dir = os.path.join(base_dir, "codes")
        
        for d in [self.frameworks_dir, self.papers_dir, self.codes_dir]:
            os.makedirs(d, exist_ok=True)
        
        # 缓存：避免每次运行都重复读文件
        self._cache = {"paper": "", "code": "", "hash": ""}
    
    def _file_hash(self) -> str:
        """计算所有训练文件的指纹，变化时自动刷新缓存"""
        import hashlib
        h = hashlib.md5()
        for cat in ("frameworks", "papers", "codes"):
            for f in self.get_file_list(cat):
                h.update(f"{cat}/{f['name']}/{f['size']}/{f['modified']}".encode())
        return h.hexdigest()
    
    def get_file_list(self, category: str) -> list:
        """获取某类训练数据的文件列表"""
        dir_map = {
            "frameworks": self.frameworks_dir,
            "papers": self.papers_dir,
            "codes": self.codes_dir,
        }
        target_dir = dir_map.get(category)
        if not target_dir or not os.path.exists(target_dir):
            return []
        
        files = []
        for f in sorted(os.listdir(target_dir)):
            full_path = os.path.join(target_dir, f)
            if os.path.isfile(full_path):
                size = os.path.getsize(full_path)
                mtime = os.path.getmtime(full_path)
                files.append({
                    "name": f,
                    "size": size,
                    "category": category,
                    "modified": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S"),
                })
        return files
    
    def get_all_stats(self) -> dict:
        """获取知识库统计信息"""
        return {
            "frameworks": len(self.get_file_list("frameworks")),
            "papers": len(self.get_file_list("papers")),
            "codes": len(self.get_file_list("codes")),
        }
    
    def save_file(self, category: str, filename: str, content: bytes) -> str:
        """保存训练数据文件"""
        dir_map = {
            "frameworks": self.frameworks_dir,
            "papers": self.papers_dir,
            "codes": self.codes_dir,
        }
        target_dir = dir_map.get(category)
        if not target_dir:
            raise ValueError(f"未知类别: {category}")
        
        filepath = os.path.join(target_dir, filename)
        with open(filepath, "wb") as f:
            f.write(content)
        self._cache["hash"] = ""  # 清缓存，下次自动重建
        return filepath
    
    def read_file(self, category: str, filename: str) -> str:
        """读取训练数据文件内容"""
        dir_map = {
            "frameworks": self.frameworks_dir,
            "papers": self.papers_dir,
            "codes": self.codes_dir,
        }
        target_dir = dir_map.get(category)
        if not target_dir:
            return ""
        
        filepath = os.path.join(target_dir, filename)
        if not os.path.exists(filepath):
            return ""
        
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ""
        
        try:
            if ext in ('txt', 'md', 'py'):
                with open(filepath, 'r', encoding='utf-8') as f:
                    return f.read()
            elif ext == 'pdf':
                try:
                    from PyPDF2 import PdfReader
                    reader = PdfReader(filepath)
                    parts = []
                    for page in reader.pages:
                        t = page.extract_text()
                        if t:
                            parts.append(t)
                    return '\n'.join(parts)
                except ImportError:
                    return ""
            else:
                return ""
        except Exception:
            return ""
    
    def delete_file(self, category: str, filename: str) -> bool:
        """删除训练数据文件"""
        dir_map = {
            "frameworks": self.frameworks_dir,
            "papers": self.papers_dir,
            "codes": self.codes_dir,
        }
        target_dir = dir_map.get(category)
        if not target_dir:
            return False
        
        filepath = os.path.join(target_dir, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            self._cache["hash"] = ""  # 清缓存
            return True
        return False

    def build_paper_context(self, max_chars_per_file: int = 3000) -> str:
        """
        构建论文参考上下文（注入到Agent1）
        读取 frameworks/ + papers/ 并拼接
        有缓存机制，文件不变时直接返回缓存
        """
        fhash = self._file_hash()
        if fhash == self._cache["hash"] and self._cache["paper"]:
            return self._cache["paper"]
        
        parts = []
        
        framework_files = self.get_file_list("frameworks")
        if framework_files:
            parts.append("## 🏗️ 论文框架模板（必须严格遵循）")
            parts.append("你在输出分析文档时，必须逐节对齐以下论文框架结构，章节标题、层级关系、内容顺序不得偏离：\n")
            for f in framework_files[:3]:
                content = self.read_file("frameworks", f["name"])
                if content:
                    parts.append(f"### 框架模板: {f['name']}")
                    parts.append(content[:max_chars_per_file])
                    parts.append("")
        
        paper_files = self.get_file_list("papers")
        if paper_files:
            parts.append("## 📖 优秀论文风格模仿（必须强制模仿）")
            parts.append("你的输出必须全面模仿以下优秀论文的写作风格，具体要求如下：\n")
            parts.append("- **措辞习惯**：模仿论文中使用的学术词汇、句式结构、段落组织方式")
            parts.append("- **公式书写**：仿照其LaTeX公式的排版风格、编号方式、变量命名习惯")
            parts.append("- **分析深度**：做到同等级别的推导详略、论据展开方式")
            parts.append("- **章节语气**：问题分析的口吻、模型假设的表述方式、结论收尾逻辑全部对齐\n")
            for f in paper_files[:5]:
                content = self.read_file("papers", f["name"])
                if content:
                    parts.append(f"### 模仿范本: {f['name']}")
                    parts.append(content[:max_chars_per_file])
                    parts.append("")
        
        result = "\n".join(parts) if parts else ""
        self._cache["paper"] = result
        self._cache["hash"] = fhash
        return result
    
    def build_code_context(self, max_chars_per_file: int = 2000) -> str:
        """
        构建代码参考上下文（注入到Agent2）
        读取 codes/ 目录下的参考代码
        有缓存机制，文件不变时直接返回缓存
        """
        fhash = self._file_hash()
        if fhash == self._cache["hash"] and self._cache["code"]:
            return self._cache["code"]
        
        code_files = self.get_file_list("codes")
        if not code_files:
            self._cache["code"] = ""
            self._cache["hash"] = fhash
            return ""
        
        parts = ["## 参考求解代码风格与模板"]
        parts.append("请参考以下代码的风格、注释规范、结构组织方式：\n")
        
        for f in code_files[:5]:
            content = self.read_file("codes", f["name"])
            if content:
                parts.append(f"### 参考文件: {f['name']}")
                parts.append(content[:max_chars_per_file])
                parts.append("")
        
        result = "\n".join(parts)
        self._cache["code"] = result
        self._cache["hash"] = fhash
        return result
