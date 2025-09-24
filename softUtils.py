import requests
import time
import json
import logging

# ===================== 日志配置 =====================
logging.basicConfig(filename='stock_monitor.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# ===================== PushPlus 推送函数 =====================
def send_pushplus(msg, token):
    url = "http://www.pushplus.plus/send"
    data = {
        "token": token,
        "title": "配对交易阈值差",
        "content": msg,
        "template": "html"
    }
    try:
        r = requests.post(url, json=data, timeout=5)
        print("PushPlus 返回:", r.status_code, r.text)
        if r.status_code != 200 or json.loads(r.text).get("code") != 200:
            logging.error(f"PushPlus 推送失败: {r.text}")
    except Exception as e:
        logging.error(f"PushPlus 推送异常: {e}")

# ===================== 获取股价及涨跌幅 =====================
def get_today_change_vs_prev_close(code):
    market = "sh" if code.startswith("6") else "sz"
    url = f"http://qt.gtimg.cn/q={market}{code}"
    try:
        r = requests.get(url, timeout=5).text
        fields = r.split('~')
        if len(fields) >= 5:
            latest_price = float(fields[3])
            prev_close = float(fields[4])
            name = fields[1]
            if prev_close != 0:
                change = (latest_price - prev_close) / prev_close
                return change, latest_price, name
    except Exception as e:
        logging.error(f"获取 {code} 涨跌幅和价格失败: {e}")
    return None, None, None

# ===================== HTML 推送消息格式 =====================
def format_push_message(stockA, stockB, priceA, priceB, nameA, nameB, changeA, changeB, spread, threshold, img_url=""):
    colorA = "red" if changeA > 0 else "green"
    colorB = "red" if changeB > 0 else "green"
    colorSpread = "red" if abs(spread) >= threshold else "black"
    img_html = f'<div style="text-align:center;"><img src="{img_url}" alt="提醒图" style="width:120px;height:auto;margin-bottom:10px;"></div>' if img_url else ""

    msg = f"""
    <div style="font-family:微软雅黑, Arial; line-height:1.5; background:#fefefe; padding:15px; border:1px solid #ddd; border-radius:10px;">
        {img_html}
        <h2 style="color:#333; text-align:center;">⚠️ 股票涨跌幅差提醒</h2>
        <table style="width:100%; border-collapse: collapse; margin-top:10px;">
            <tr>
                <th style="text-align:left; padding:5px;">股票</th>
                <th style="text-align:left; padding:5px;">公司</th>
                <th style="text-align:left; padding:5px;">最新价</th>
                <th style="text-align:left; padding:5px;">今日涨幅</th>
            </tr>
            <tr style="border-top:1px solid #ccc;">
                <td style="padding:5px;"><b>{stockA}</b></td>
                <td style="padding:5px; color:#555;">{nameA}</td>
                <td style="padding:5px;"><b>{priceA:.2f}</b></td>
                <td style="padding:5px; color:{colorA};">{changeA:.2%}</td>
            </tr>
            <tr style="border-top:1px solid #ccc;">
                <td style="padding:5px;"><b>{stockB}</b></td>
                <td style="padding:5px; color:#555;">{nameB}</td>
                <td style="padding:5px;"><b>{priceB:.2f}</b></td>
                <td style="padding:5px; color:{colorB};">{changeB:.2%}</td>
            </tr>
        </table>
        <div style="margin-top:10px; font-size:16px;">
            <b>差值:</b> <span style="color:{colorSpread}; font-size:18px;">{spread:.2%}</span> （阈值: {threshold:.2%}）
        </div>
        <div style="margin-top:10px; font-size:12px; color:#999;">
            更新时间: {time.strftime("%Y-%m-%d %H:%M:%S")}
        </div>
    </div>
    """
    return msg

# ===================== 读取配置文件 =====================
def load_config(file_path="config.json"):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"读取配置文件失败: {e}")
        return None

# ===================== 批量监控 =====================
def monitor_stock_pairs(pairs, token, threshold=0.02, interval=60, img_url=""):
    logging.info(f"开始批量监控 {len(pairs)} 对股票，每 {interval} 秒检查一次")
    while True:
        try:
            for stockA, stockB in pairs:
                changeA, priceA, nameA = get_today_change_vs_prev_close(stockA)
                changeB, priceB, nameB = get_today_change_vs_prev_close(stockB)

                if changeA is None or changeB is None:
                    continue

                spread = changeA - changeB
                logging.info(f"{stockA}({priceA:.2f}, {changeA:.2%}) vs {stockB}({priceB:.2f}, {changeB:.2%}), 差值: {spread:.2%}")
                print(f"[{time.strftime('%H:%M:%S')}] {stockA}({priceA:.2f}, {changeA:.2%}) vs {stockB}({priceB:.2f}, {changeB:.2%}), 差值: {spread:.2%}")

                if abs(spread) >= threshold:
                    alert_msg = format_push_message(
                        stockA, stockB, priceA, priceB, nameA, nameB,
                        changeA, changeB, spread, threshold, img_url
                    )
                    send_pushplus(alert_msg, token)

            time.sleep(interval)
        except KeyboardInterrupt:
            logging.info("监控结束")
            print("监控结束")
            break
        except Exception as e:
            logging.error(f"监控异常: {e}")
            time.sleep(interval)

# ===================== 主函数 =====================
if __name__ == "__main__":
    config = load_config("config.json")
    if not config:
        print("读取配置失败，请检查 config.json")
        exit(1)

    stock_pairs = config.get("stock_pairs", [])
    threshold = config.get("threshold", 0.02)
    interval = config.get("interval", 60)
    pushplus_token = config.get("pushplus_token", "")
    img_url = config.get("img_url", "")  # 可选图片 URL

    if not stock_pairs or not pushplus_token:
        print("请在 config.json 中配置 stock_pairs 和 pushplus_token")
        exit(1)

    monitor_stock_pairs(stock_pairs, pushplus_token, threshold, interval, img_url)
