"""
文件处理工具
处理赛题文件上传、附件数据读取、输出文件打包与清理
"""

import os
import pandas as pd


ALLOWED_EXTENSIONS = {
    'txt', 'pdf', 'doc', 'docx', 'md',
    'xlsx', 'xls', 'csv', 'json',
    'png', 'jpg', 'jpeg', 'bmp',
    'zip', 'rar', '7z'
}

ALLOWED_DATA_EXTENSIONS = {'xlsx', 'xls', 'csv', 'json'}


def allowed_file(filename: str) -> bool:
    """检查文件类型是否允许上传"""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def is_data_file(filename: str) -> bool:
    """判断是否为数据类附件"""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_DATA_EXTENSIONS


def read_data_file(filepath: str) -> str:
    """读取数据文件并返回数据概览描述"""
    if not os.path.exists(filepath):
        return ""
    
    ext = filepath.rsplit('.', 1)[1].lower() if '.' in filepath else ""
    
    try:
        if ext in ('csv',):
            df = pd.read_csv(filepath, encoding='utf-8')
        elif ext in ('xlsx', 'xls'):
            df = pd.read_excel(filepath)
        elif ext == 'json':
            df = pd.read_json(filepath)
        else:
            return ""
        
        desc_parts = []
        desc_parts.append(f"文件名: {os.path.basename(filepath)}")
        desc_parts.append(f"数据形状: {df.shape[0]} 行 × {df.shape[1]} 列")
        desc_parts.append(f"列名: {', '.join(df.columns.tolist())}")
        desc_parts.append(f"数据类型概览:\n{df.dtypes.to_string()}")
        desc_parts.append(f"前5行预览:\n{df.head(5).to_string()}")
        desc_parts.append(f"基本统计:\n{df.describe(include='all').to_string()}")
        
        missing = df.isnull().sum()
        missing_cols = missing[missing > 0]
        if len(missing_cols) > 0:
            desc_parts.append(f"缺失值情况:\n{missing_cols.to_string()}")
        else:
            desc_parts.append("缺失值: 无")
        
        return "\n\n".join(desc_parts)
    
    except Exception as e:
        return f"数据文件读取失败: {str(e)}"


def read_problem_file(filepath: str) -> str:
    """读取赛题文本文件内容"""
    if not os.path.exists(filepath):
        return ""
    
    ext = filepath.rsplit('.', 1)[1].lower() if '.' in filepath else ""
    
    try:
        if ext in ('txt', 'md'):
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        elif ext == 'pdf':
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(filepath)
                text_parts = []
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                if text_parts:
                    return '\n'.join(text_parts)
                return "[提示: PDF无文字内容，请确认是否为扫描版PDF]"
            except ImportError:
                return "[提示: 需安装 PyPDF2 才能读取 PDF 文件]"
        elif ext == 'docx':
            try:
                import docx
                doc = docx.Document(filepath)
                return '\n'.join([p.text for p in doc.paragraphs])
            except ImportError:
                return "[提示: 需安装 python-docx 才能读取 .docx 文件]"
        elif ext == 'doc':
            return "[提示: .doc 格式暂不支持，请转为 .docx 或 .txt 后上传]"
        else:
            return ""
    except Exception as e:
        return f"文件读取失败: {str(e)}"


def cleanup_old_outputs(output_dir: str, max_age_hours: int = 24):
    """清理过期的输出文件"""
    import time
    import shutil
    
    if not os.path.exists(output_dir):
        return
    
    cutoff = time.time() - max_age_hours * 3600
    for item in os.listdir(output_dir):
        item_path = os.path.join(output_dir, item)
        if os.path.getmtime(item_path) < cutoff:
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)
