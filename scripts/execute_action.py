#!/usr/bin/env python3
"""
执行单个 UI 操作
"""
import argparse
import json
import sys
import time

try:
    import uiautomator2 as u2
except ImportError:
    print("Error: uiautomator2 not installed", file=sys.stderr)
    sys.exit(1)


def find_element(d, target: dict):
    """根据 target 描述定位元素"""
    # 优先级: text > content_desc > resource_id
    if 'text' in target:
        elem = d(text=target['text'])
        if elem.exists:
            return elem

    if 'content_desc' in target:
        elem = d(description=target['content_desc'])
        if elem.exists:
            return elem

    if 'resource_id' in target:
        elem = d(resourceId=target['resource_id'])
        if elem.exists:
            return elem

    # 组合条件
    kwargs = {}
    if 'className' in target:
        kwargs['className'] = target['className']
    if 'index' in target:
        kwargs['index'] = target['index']

    if kwargs:
        if 'text' in target:
            kwargs['text'] = target['text']
        elem = d(**kwargs)
        if elem.exists:
            return elem

    return None


def execute_action(device_id: str, action: str, target: dict, value: str = None) -> dict:
    """执行操作"""
    start = time.time()

    try:
        d = u2.connect(device_id) if device_id else u2.connect()
    except Exception as e:
        return {'success': False, 'error': f'Connect failed: {e}'}

    result = {'action': action, 'target': target}

    try:
        if action == 'click':
            elem = find_element(d, target)
            if elem:
                elem.click()
                result['success'] = True
            else:
                result['success'] = False
                result['error'] = 'Element not found'

        elif action == 'input':
            elem = find_element(d, target)
            if elem:
                elem.set_text(value or '')
                result['success'] = True
            else:
                result['success'] = False
                result['error'] = 'Element not found'

        elif action == 'swipe':
            # target 格式: {"from": [x1,y1], "to": [x2,y2]}
            d.swipe(target['from'][0], target['from'][1],
                    target['to'][0], target['to'][1])
            result['success'] = True

        elif action == 'tap':
            # 直接坐标点击
            d.click(target['x'], target['y'])
            result['success'] = True

        elif action == 'back':
            d.press('back')
            result['success'] = True

        elif action == 'home':
            d.press('home')
            result['success'] = True

        elif action == 'wait':
            time.sleep(float(value or 1))
            result['success'] = True

        else:
            result['success'] = False
            result['error'] = f'Unknown action: {action}'

    except Exception as e:
        result['success'] = False
        result['error'] = str(e)

    result['time'] = round(time.time() - start, 3)
    return result


def main():
    parser = argparse.ArgumentParser(description='Execute UI action')
    parser.add_argument('--device', '-d', help='Device ID')
    parser.add_argument('--action', '-a', required=True,
                        choices=['click', 'input', 'swipe', 'tap', 'back', 'home', 'wait'])
    parser.add_argument('--target', '-t', help='Target element (JSON)')
    parser.add_argument('--value', '-v', help='Value for input/wait')
    args = parser.parse_args()

    target = json.loads(args.target) if args.target else {}
    result = execute_action(args.device, args.action, target, args.value)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
