import json
import os
import glob

# 设置目录路径
dir_path = "."

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

# 按照图片生成颠倒的markdown表格
for image_name, boxes in image_boxes.items():
    markdown_content += f"## {image_name}\n\n"
    
    # 生成颠倒的表格
    # 表格头：翻译引擎 + 各个原始文本片段的索引
    # 首先准备所有的box索引和原始文本
    box_info = []
    for i, box in enumerate(boxes):
        box_info.append((i+1, box['original_text'], box['key']))
    
    # 表格头：翻译引擎 + 每个box的索引（显示为序号和原始文本）
    headers = ["翻译引擎"]
    for idx, original_text, _ in box_info:
        headers.append(f"{idx}. {original_text}")
    
    markdown_content += "| " + " | ".join(headers) + " |\n"
    markdown_content += "| " + " | ".join(["---"] * len(headers)) + " |\n"
    
    # 表格行：每个翻译引擎一行
    for engine_name in translations.keys():
        row = [engine_name]
        for _, _, key in box_info:
            translation = translations[engine_name].get(key, "")
            row.append(translation)
        # 转义表格中的特殊字符
        row = [cell.replace("|", "\\|") for cell in row]
        markdown_content += "| " + " | ".join(row) + " |\n"
    
    markdown_content += "\n"

# 输出到markdown文件
output_file = "translation_comparison.md"
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(markdown_content)

print(f"翻译结果已输出到 {output_file}")