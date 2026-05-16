"""
数学建模竞赛总调度智能体 - Flask Web 后端
基于 DeepSeek V4 Pro，双Agent协同完成数模全流程
"""

import os
import json
import queue
import threading
from datetime import datetime

from flask import (
    Flask, render_template, request, jsonify, 
    send_file, Response, stream_with_context
)
from flask_cors import CORS
from dotenv import load_dotenv

from agents.orchestrator import Orchestrator
from utils.file_handler import (
    allowed_file, is_data_file, read_data_file, 
    read_problem_file, cleanup_old_outputs
)
from utils.knowledge_base import KnowledgeBase

kb = KnowledgeBase()

load_dotenv()

app = Flask(__name__)
CORS(app)

app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['OUTPUT_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'outputs')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# 进度队列 - 用于SSE推送
progress_queues = {}


@app.route('/')
def index():
    """渲染主页"""
    return render_template('index.html')


@app.route('/api/check-config')
def check_config():
    """检查API配置状态"""
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    has_key = bool(api_key and api_key != "your_deepseek_api_key_here")
    return jsonify({
        "configured": has_key,
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"),
    })


@app.route('/api/upload', methods=['POST'])
def upload_and_process():
    """上传赛题文件和附件数据，启动处理流程"""
    
    problem_file = request.files.get('problem_file')
    if not problem_file or not problem_file.filename:
        return jsonify({"error": "请上传赛题文件"}), 400
    
    if not allowed_file(problem_file.filename):
        return jsonify({"error": "赛题文件格式不支持，支持 .txt .md .docx .pdf"}), 400
    
    problem_text = ""
    
    # 保存并读取赛题文件
    problem_filename = problem_file.filename
    problem_filepath = os.path.join(app.config['UPLOAD_FOLDER'], problem_filename)
    problem_file.save(problem_filepath)
    
    content = read_problem_file(problem_filepath)
    if content and not content.startswith("[提示:") and len(content.strip()) > 50:
        problem_text = content
    elif content and content.startswith("[提示:"):
        return jsonify({"error": f"无法解析赛题文件内容: {content}"}), 400
    else:
        # PDF 解析后文件内容截图
        problem_text = f"【赛题文件: {problem_filename}】\n文件大小: {problem_file.content_length} bytes\n注意: 文件内容解析异常，请确认文件非扫描版PDF或加密文件。"
    
    # 读取附件数据文件
    data_description = ""
    data_files = request.files.getlist('data_files')
    for file in data_files:
        if file.filename and allowed_file(file.filename):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)
            
            if is_data_file(file.filename):
                data_description += read_data_file(filepath) + "\n\n"
            else:
                more = read_problem_file(filepath)
                if more:
                    data_description += f"【附件: {file.filename}】\n{more}\n\n"
    
    task_id = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    
    progress_queues[task_id] = queue.Queue()
    
    thread = threading.Thread(
        target=_run_orchestration,
        args=(task_id, problem_text, data_description),
        daemon=True
    )
    thread.start()
    
    return jsonify({"task_id": task_id, "status": "started"})


def _run_orchestration(task_id: str, problem_text: str, data_description: str):
    """在后台线程中执行编排流程"""
    q = progress_queues.get(task_id)
    
    def progress_callback(stage, message):
        if q:
            q.put(json.dumps({"stage": stage, "message": message}))
    
    orchestrator = Orchestrator(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    )
    
    try:
        results = orchestrator.run(
            problem_text=problem_text,
            data_description=data_description,
            progress_callback=progress_callback
        )
        if q:
            q.put(json.dumps({
                "stage": "complete",
                "message": "处理完成",
                "result": {
                    "analysis_doc": results.get("analysis_doc", ""),
                    "code_files": results.get("code_files", {}),
                    "zip_path": results.get("zip_path", ""),
                    "task_id": task_id,
                }
            }))
    except Exception as e:
        if q:
            q.put(json.dumps({
                "stage": "error",
                "message": f"处理失败: {str(e)}"
            }))
    finally:
        if q:
            q.put(json.dumps({"stage": "stream_end"}))


@app.route('/api/progress/<task_id>')
def get_progress(task_id):
    """SSE推送处理进度"""
    q = progress_queues.get(task_id)
    if not q:
        return jsonify({"error": "任务不存在"}), 404
    
    def generate():
        while True:
            try:
                msg = q.get(timeout=300)
                yield f"data: {msg}\n\n"
                data = json.loads(msg)
                if data.get("stage") in ("stream_end", "error"):
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'stage': 'timeout', 'message': '处理超时'})}\n\n"
                break
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        }
    )


@app.route('/api/download/<task_id>')
def download_result(task_id):
    """下载结果zip包"""
    outputs_dir = app.config['OUTPUT_FOLDER']
    for item in os.listdir(outputs_dir):
        if item.startswith(f"mcm_solution_") and item.endswith(".zip"):
            zip_path = os.path.join(outputs_dir, item)
            if os.path.exists(zip_path):
                return send_file(
                    zip_path,
                    as_attachment=True,
                    download_name=f"数模竞赛方案_{task_id}.zip"
                )
    
    return jsonify({"error": "文件不存在或已过期"}), 404


@app.route('/api/result/<task_id>')
def get_result(task_id):
    """获取处理结果（不含文件下载）"""
    outputs_dir = app.config['OUTPUT_FOLDER']
    for item in os.listdir(outputs_dir):
        folder_path = os.path.join(outputs_dir, item)
        if item.startswith("mcm_solution_") and os.path.isdir(folder_path):
            analysis_path = os.path.join(folder_path, "problem_analysis.md")
            analysis_content = ""
            if os.path.exists(analysis_path):
                with open(analysis_path, "r", encoding="utf-8") as f:
                    analysis_content = f.read()
            
            code_files = {}
            for f in os.listdir(folder_path):
                if f.endswith(".py"):
                    with open(os.path.join(folder_path, f), "r", encoding="utf-8") as cf:
                        code_files[f] = cf.read()
            
            zip_filename = f"数模竞赛方案_{task_id}.zip"
            
            return jsonify({
                "analysis_doc": analysis_content,
                "code_files": code_files,
                "zip_filename": zip_filename,
            })
    
    return jsonify({"error": "结果不存在"}), 404


@app.route('/api/training/stats')
def training_stats():
    """获取知识库统计信息"""
    return jsonify(kb.get_all_stats())


@app.route('/api/training/list')
def training_list():
    """获取知识库文件列表"""
    return jsonify({
        "frameworks": kb.get_file_list("frameworks"),
        "papers": kb.get_file_list("papers"),
        "codes": kb.get_file_list("codes"),
    })


@app.route('/api/training/upload', methods=['POST'])
def training_upload():
    """上传训练数据到知识库"""
    category = request.form.get('category', '').strip()
    if category not in ('frameworks', 'papers', 'codes'):
        return jsonify({"error": "类别必须为 frameworks/papers/codes"}), 400
    
    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({"error": "请选择文件"}), 400
    
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ('txt', 'md', 'pdf', 'py'):
        return jsonify({"error": f"不支持的文件格式: .{ext}，支持 .txt .md .pdf .py"}), 400
    
    content = file.read()
    filepath = kb.save_file(category, file.filename, content)
    
    return jsonify({
        "success": True,
        "category": category,
        "filename": file.filename,
        "path": filepath,
    })


@app.route('/api/training/read', methods=['GET'])
def training_read():
    """读取训练数据文件内容"""
    category = request.args.get('category', '').strip()
    filename = request.args.get('filename', '').strip()
    
    if category not in ('frameworks', 'papers', 'codes'):
        return jsonify({"error": "类别无效"}), 400
    
    content = kb.read_file(category, filename)
    if not content:
        return jsonify({"error": "文件不存在"}), 404
    
    return jsonify({"content": content, "filename": filename, "category": category})


@app.route('/api/training/delete', methods=['POST'])
def training_delete():
    """删除训练数据文件"""
    data = request.get_json()
    category = data.get('category', '').strip()
    filename = data.get('filename', '').strip()
    
    if category not in ('frameworks', 'papers', 'codes'):
        return jsonify({"error": "类别无效"}), 400
    
    if kb.delete_file(category, filename):
        return jsonify({"success": True})
    return jsonify({"error": "文件不存在"}), 404


if __name__ == '__main__':
    cleanup_old_outputs(app.config['OUTPUT_FOLDER'])
    app.run(host='0.0.0.0', port=5000, debug=False)
