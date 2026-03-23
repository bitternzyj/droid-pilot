#!/usr/bin/env python3
"""
获取当前屏幕上下文，返回可操作元素列表
"""
import argparse
import json
import re
import sys
import time

try:
    import uiautomator2 as u2
except ImportError:
    print("Error: uiautomator2 not installed. Run: pip install uiautomator2", file=sys.stderr)
    sys.exit(1)


def parse_bounds(bounds_str: str) -> list:
    """解析 bounds 字符串 [left,top][right,bottom] -> [left, top, right, bottom]"""
    match = re.findall(r'\[(\d+),(\d+)\]', bounds_str)
    if len(match) == 2:
        return [int(match[0][0]), int(match[0][1]), int(match[1][0]), int(match[1][1])]
    return []


def extract_elements(d, app_package: str = None) -> list:
    """从 u2 设备提取可操作元素"""
    import xml.etree.ElementTree as ET

    start = time.time()
    xml = d.dump_hierarchy()
    dump_time = time.time() - start

    elements = []
    root = ET.fromstring(xml)

    for node in root.iter('node'):
        # 过滤非目标应用的元素（状态栏等）
        package = node.get('package', '')
        if app_package and package and package != app_package:
            continue

        # 提取关键属性
        text = (node.get('text') or '').strip()
        content_desc = (node.get('content-desc') or '').strip()
        resource_id = node.get('resource-id') or ''
        clickable = node.get('clickable') == 'true'
        checkable = node.get('checkable') == 'true'
        checked = node.get('checked') == 'true'
        selected = node.get('selected')
        bounds = node.get('bounds') or ''
        cls = node.get('class') or ''

        # 只保留有意义的元素
        has_identity = text or content_desc or resource_id
        is_interactive = clickable or checkable

        if not (has_identity or is_interactive):
            continue

        # 推断元素类型
        if 'Button' in cls:
            elem_type = 'button'
        elif 'CheckBox' in cls or checkable:
            elem_type = 'checkbox'
        elif 'EditText' in cls:
            elem_type = 'input'
        elif 'TextView' in cls:
            elem_type = 'tab' if selected == 'true' else 'text'
        elif 'ImageView' in cls:
            elem_type = 'image'
        elif 'RecyclerView' in cls or 'ListView' in cls:
            elem_type = 'list'
        elif 'ScrollView' in cls:
            elem_type = 'scroll'
        else:
            elem_type = 'view'

        elem = {
            'type': elem_type,
            'bounds': parse_bounds(bounds) if bounds else [],
        }

        if text:
            elem['text'] = text
        if content_desc:
            elem['content_desc'] = content_desc
        if resource_id:
            elem['resource_id'] = resource_id.split('/')[-1]
        if clickable:
            elem['clickable'] = True
        if checkable:
            elem['checkable'] = True
            elem['checked'] = checked
        if selected == 'true':
            elem['selected'] = True

        elements.append(elem)

    return elements, dump_time


def get_screen_context(device_id: str = None) -> dict:
    """获取完整屏幕上下文"""
    try:
        d = u2.connect(device_id) if device_id else u2.connect()
    except Exception as e:
        return {'error': f'Failed to connect: {e}'}

    # 获取基本信息
    info = d.info
    current_app = d.app_current()

    # 提取元素（只保留当前应用的）
    elements, dump_time = extract_elements(d, app_package=current_app.get('package'))

    return {
        'device': device_id or 'default',
        'package': current_app.get('package', ''),
        'activity': current_app.get('activity', '').split('.')[-1],
        'screen_size': [info.get('displayWidth', 0), info.get('displayHeight', 0)],
        'dump_time': round(dump_time, 3),
        'element_count': len(elements),
        'elements': elements
    }


def main():
    parser = argparse.ArgumentParser(description='Get screen context')
    parser.add_argument('--device', '-d', help='Device ID')
    parser.add_argument('--format', '-f', choices=['json', 'text'], default='json')
    parser.add_argument('--compact', '-c', action='store_true', help='Compact output')
    args = parser.parse_args()

    context = get_screen_context(args.device)

    if args.format == 'json':
        indent = None if args.compact else 2
        print(json.dumps(context, ensure_ascii=False, indent=indent))
    else:
        # 文本格式，更易读
        print(f"Package: {context.get('package')}")
        print(f"Activity: {context.get('activity')}")
        print(f"Dump time: {context.get('dump_time')}s")
        print(f"\nElements ({context.get('element_count')}):")
        for elem in context.get('elements', []):
            ident = elem.get('text') or elem.get('content_desc') or elem.get('resource_id', '')
            flags = []
            if elem.get('clickable'):
                flags.append('clickable')
            if elem.get('checkable'):
                flags.append(f"checkbox:{'checked' if elem.get('checked') else 'unchecked'}")
            if elem.get('selected'):
                flags.append('selected')
            print(f"  [{elem['type']}] {ident} {' '.join(flags)}")


if __name__ == '__main__':
    main()
