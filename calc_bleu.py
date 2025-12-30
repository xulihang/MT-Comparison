import json
import os
import glob
import nltk
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction

# 确保下载了必要的nltk资源
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

# 计算BLEU分数的函数
def calculate_bleu(reference_text, candidate_text):
    if not reference_text or not candidate_text:
        return 0.0
    
    # 分词 - 对于不同语言使用不同的分词策略
    if any(ord(c) > 127 for c in reference_text):  # 检查是否包含非ASCII字符（可能是中文）
        # 对于中文等语言，按字符分词
        reference = list(reference_text)
        candidate = list(candidate_text)
    else:
        # 对于英文等语言，使用nltk分词
        reference = nltk.word_tokenize(reference_text.lower())
        candidate = nltk.word_tokenize(candidate_text.lower())
    
    # 使用平滑函数避免零分
    smoothie = SmoothingFunction().method1
    
    try:
        # BLEU分数计算
        bleu_score = sentence_bleu([reference], candidate, smoothing_function=smoothie)
        return bleu_score
    except:
        return 0.0

# 处理单个目录的函数
def process_directory(dir_path):
    # 获取所有itp文件
    itp_files = glob.glob(os.path.join(dir_path, "*.itp"))
    
    # 准备markdown输出内容
    markdown_content = "# 翻译结果比较\n\n"
    
    # 首先，收集所有文件的翻译数据
    translations = {}
    image_boxes = {}
    
    # 遍历所有itp文件，收集翻译数据
    for itp_file in itp_files:
        # 获取文件名（不含扩展名）作为翻译引擎名称
        engine_name = os.path.splitext(os.path.basename(itp_file))[0]
        translations[engine_name] = {}
        
        # 读取并解析JSON文件
        try:
            with open(itp_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 遍历images中的每个图片
            for image_name, image_data in data.get('images', {}).items():
                # 跳过临时文件和空boxes
                if 'tmp' in image_name or not image_data.get('boxes'):
                    continue
                
                if image_name not in image_boxes:
                    image_boxes[image_name] = []
                
                # 遍历当前图片的所有boxes，收集target
                for box_idx, box in enumerate(image_data['boxes']):
                    target = box.get('target', '')
                    # 构建唯一键（图片名+box索引）
                    key = f"{image_name}_{box_idx}"
                    translations[engine_name][key] = target
                    
                    # 如果是第一次遇到这个box，添加到image_boxes中
                    if len(image_boxes[image_name]) <= box_idx:
                        image_boxes[image_name].append({
                            'key': key,
                            'original_text': box.get('text', '')
                        })
        except Exception as e:
            print(f"处理文件 {itp_file} 时出错: {e}")
    
    # 查找human开头的参考翻译文件
    human_refs = {}
    for engine_name in translations.keys():
        if engine_name.startswith('human'):
            human_refs[engine_name] = translations[engine_name]
    
    # 按照图片生成颠倒的markdown表格
    for image_name, boxes in image_boxes.items():
        markdown_content += f"## {image_name}\n\n"
        
        # 生成颠倒的表格
        # 表格头：翻译引擎 + 各个原始文本片段的索引
        box_info = []
        for i, box in enumerate(boxes):
            box_info.append((i+1, box['original_text'], box['key']))
        
        # 表格头：翻译引擎 + 每个box的索引
        headers = ["翻译引擎"]
        for idx, original_text, _ in box_info:
            headers.append(f"{idx}. {original_text}")
        
        # 如果有参考翻译，添加BLEU评分列
        if human_refs:
            for ref_name in human_refs.keys():
                headers.append(f"BLEU@{ref_name}")
        
        markdown_content += "| " + " | ".join(headers) + " |\n"
        markdown_content += "| " + " | ".join(["---"] * len(headers)) + " |\n"
        
        # 表格行：每个翻译引擎一行，为每个图片计算分数并排序
        # 先计算每个引擎的分数
        engine_scores = []
        for engine_name in translations.keys():
            row_data = {'name': engine_name, 'row': [engine_name], 'avg_score': 0}
            
            # 添加每个box的翻译
            for _, _, key in box_info:
                translation = translations[engine_name].get(key, "")
                row_data['row'].append(translation)
            
            # 计算BLEU评分
            bleu_values = []
            if human_refs:
                for ref_name, ref_translations in human_refs.items():
                    # 计算当前引擎相对于该参考的平均BLEU分数
                    bleu_scores = []
                    for _, _, key in box_info:
                        ref_text = ref_translations.get(key, "")
                        cand_text = translations[engine_name].get(key, "")
                        bleu_score = calculate_bleu(ref_text, cand_text)
                        bleu_scores.append(bleu_score)
                    
                    # 计算平均BLEU分数并格式化
                    if bleu_scores:
                        avg_bleu = sum(bleu_scores) / len(bleu_scores)
                        row_data['row'].append(f"{avg_bleu:.4f}")
                        bleu_values.append(avg_bleu)
                    else:
                        row_data['row'].append("0.0000")
            
            # 计算平均分用于排序
            if bleu_values:
                row_data['avg_score'] = sum(bleu_values) / len(bleu_values)
            engine_scores.append(row_data)
        
        # 按平均分降序排序
        engine_scores.sort(key=lambda x: x['avg_score'], reverse=True)
        
        # 输出排序后的行
        for engine in engine_scores:
            row = engine['row']
            # 转义表格中的特殊字符
            row = [cell.replace("|", "\\|") for cell in row]
            markdown_content += "| " + " | ".join(row) + " |\n"
        
        markdown_content += "\n"
    
    # 生成总体BLEU评分汇总
    if human_refs:
        markdown_content += "## 总体BLEU评分汇总\n\n"
        # 添加平均分列
        markdown_content += "| 翻译引擎 | " + " | ".join([f"BLEU@{ref_name}" for ref_name in human_refs.keys()]) + " | 平均分 |\n"
        markdown_content += "| " + " | ".join(["---"] * (len(human_refs) + 2)) + " |\n"
        
        # 计算每个引擎的总体BLEU分数并存储
        engine_scores = []
        for engine_name in translations.keys():
            row_data = {'name': engine_name, 'scores': [], 'avg_score': 0}
            
            for ref_name, ref_translations in human_refs.items():
                # 收集所有共同的键并计算BLEU
                common_keys = set(translations[engine_name].keys()) & set(ref_translations.keys())
                bleu_scores = []
                
                for key in common_keys:
                    ref_text = ref_translations[key]
                    cand_text = translations[engine_name][key]
                    bleu_score = calculate_bleu(ref_text, cand_text)
                    bleu_scores.append(bleu_score)
                
                if bleu_scores:
                    avg_bleu = sum(bleu_scores) / len(bleu_scores)
                    row_data['scores'].append(f"{avg_bleu:.4f}")
                    row_data['avg_score'] += avg_bleu  # 累加用于计算平均分
                else:
                    row_data['scores'].append("0.0000")
            
            # 计算平均分
            if row_data['scores']:
                # 过滤掉非数字的分数（如"0.0000"字符串需要转换）
                numeric_scores = []
                for score_str in row_data['scores']:
                    try:
                        numeric_scores.append(float(score_str))
                    except ValueError:
                        continue
                
                if numeric_scores:
                    row_data['avg_score'] = sum(numeric_scores) / len(numeric_scores)
                else:
                    row_data['avg_score'] = 0
            
            engine_scores.append(row_data)
        
        # 按平均分降序排序
        engine_scores.sort(key=lambda x: x['avg_score'], reverse=True)
        
        # 输出排序后的结果
        for engine in engine_scores:
            row = [engine['name']] + engine['scores'] + [f"{engine['avg_score']:.4f}"]
            row = [cell.replace("|", "\\|") for cell in row]
            markdown_content += "| " + " | ".join(row) + " |\n"
    
    # 输出到markdown文件
    output_file = os.path.join(dir_path, "translation_comparison.md")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    
    print(f"翻译结果和BLEU评分已输出到 {output_file}")

# 主函数
if __name__ == "__main__":
    # 处理ja2en和ja2zh两个文件夹
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    for subdir in ["manga/ja2en", "manga/ja2zh"]:
        dir_path = os.path.join(project_root, subdir)
        if os.path.exists(dir_path):
            print(f"处理目录: {dir_path}")
            process_directory(dir_path)
        else:
            print(f"目录不存在: {dir_path}")