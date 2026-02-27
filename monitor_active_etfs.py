from abc import ABC, abstractmethod
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import os
import time
import sys

# Ensure output directory exists
OUTPUT_DIR = "etf_data"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

class ETFScraper(ABC):
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7'
        }

    @abstractmethod
    def fetch_holdings(self, etf_code):
        pass

    def save_debug_html(self, etf_code, html_content):
        filename = f"{OUTPUT_DIR}/debug_{etf_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"[DEBUG] Saved HTML to {filename}")

class UnifiedScraper(ETFScraper):
    def fetch_holdings(self, etf_code):
        # Target URL for Unified ETF (EZMoney)
        # Note: ETF code '00981A' maps to internal ID '49YTW'
        # Found via manual browser navigation
        url_map = {
            '00981A': 'https://www.ezmoney.com.tw/ETF/Fund/Info?fundCode=49YTW'
        }
        
        url = url_map.get(etf_code)
        if not url:
            print(f"找不到 {etf_code} 的對應網址，請更新 url_map。")
            return None

        print(f"正在抓取 {url}...（可能需要一些時間）")
        
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"取得 {etf_code} 資料時發生錯誤：{e}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Heuristic: Find table with '股票名稱' and '比例' headers
        # Unified site structure might change, so we search for keywords.
        tables = soup.find_all('table')
        target_table = None
        for table in tables:
            text = table.get_text()
            # Keywords often found in holdings tables
            if '股票名稱' in text and ('比例' in text or '權重' in text or '股數' in text):
                target_table = table
                break
        
        if not soup.find('div', id='DataAsset'):
            print(f"找不到 {etf_code} 的 DataAsset 區塊，正在儲存 HTML 以供除錯...")
            self.save_debug_html(etf_code, response.text)
            return None
            
        try:
            import json
            import html
            
            data_div = soup.find('div', id='DataAsset')
            json_str = html.unescape(data_div['data-content'])
            data = json.loads(json_str)
            
            # Find the stock assets
            holdings = []
            for item in data:
                if item.get('AssetCode') == 'ST' and 'Details' in item:
                    for detail in item['Details']:
                        holdings.append({
                            'stock_id': detail.get('DetailCode', '').strip(),
                            'stock_name': detail.get('DetailName', '').strip(),
                            'shares': float(detail.get('Share', 0)),
                            'weight': float(detail.get('NavRate', 0)),
                            'amount': float(detail.get('Amount', 0))
                        })
            
            if not holdings:
                print(f"在 {etf_code} 的 JSON 資料中找不到股票持倉")
                return None
                
            return pd.DataFrame(holdings)
            
        except Exception as e:
            print(f"解析 {etf_code} 的 JSON 資料時發生錯誤：{e}")
            self.save_debug_html(etf_code, response.text)
            return None

def monitor_etfs():
    print("開始執行主動型 ETF 監控程式...")
    print(f"輸出目錄：{os.path.abspath(OUTPUT_DIR)}")
    
    # Active ETFs List
    # Users can add more here
    target_etfs = [
        {'code': '00981A', 'scraper': UnifiedScraper()},
        # Placeholder for other scrapers
        # {'code': '00980A', 'scraper': NomuraScraper()}, 
    ]
    
    all_data = []
    
    for etf in target_etfs:
        scraper = etf['scraper']
        print(f"正在處理 {etf['code']}...")
        df = scraper.fetch_holdings(etf['code'])
        if df is not None and not df.empty:
            all_data.append(df)
            print(f"成功取得 {etf['code']} 的 {len(df)} 筆成分股資料")
            print(df.head()) # 顯示預覽
        else:
            print(f"無法取得 {etf['code']} 的資料")
            
    if all_data:
        final_df = pd.concat(all_data)
        
        # Save current data
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = os.path.join(OUTPUT_DIR, f'etf_holdings_{timestamp}.csv')
        final_df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"\n[成功] 已儲存合併資料至：{filename}")
        
        # Comparison Logic
        try:
            # Find previous file
            files = sorted([f for f in os.listdir(OUTPUT_DIR) if f.startswith('etf_holdings_') and f.endswith('.csv')])
            if len(files) >= 2:
                prev_file = os.path.join(OUTPUT_DIR, files[-2]) # Second to last is previous
                curr_file = os.path.join(OUTPUT_DIR, files[-1]) # Last is current
                
                print(f"[資訊] 正在比較 {curr_file} 與 {prev_file}...")
                
                df_curr = pd.read_csv(curr_file)
                df_prev = pd.read_csv(prev_file)
                
                # Perform comparison for each ETF
                etfs = df_curr['ETF'].unique() if 'ETF' in df_curr.columns else ['00981A'] 
                # Note: UnifiedScraper didn't add 'ETF' column in previous step, let's ensure it does or handle it.
                # Actually scraper output dataframe didn't have ETF code column in the JSON fix. 
                # We need to add it in the scraper or here. 
                # Let's fix the scraper return first or add it here.
                # Since we are concatenated, if we didn't add ETF col in scraper, we might lose distinction if multiple ETFs.
                # But currently only 00981A. 
                
                # Let's assume one ETF for now, or add column if missing
                if 'ETF' not in final_df.columns:
                     final_df['ETF'] = '00981A' # Default for now
                
                diff_data = compare_holdings(df_curr, df_prev)
                generate_html_report(diff_data, timestamp)
                
            else:
                print("[資訊] 歷史資料不足，無法進行比較（至少需要 2 天的資料）。")
        except Exception as e:
            print(f"[錯誤] 比較作業失敗：{e}")
            import traceback
            traceback.print_exc()

        return final_df
    else:
        print("\n[警告] 未能從任何來源取得資料。")
    return None

def compare_holdings(df_curr, df_prev):
    """
    Compare current and previous holdings.
    Returns a dictionary of changes.
    """
    changes = {}
    
    # Ensure ETF column exists
    if 'ETF' not in df_curr.columns: df_curr['ETF'] = '00981A'
    if 'ETF' not in df_prev.columns: df_prev['ETF'] = '00981A'
    
    etfs = df_curr['ETF'].unique()
    
    for etf in etfs:
        curr_etf = df_curr[df_curr['ETF'] == etf].set_index('stock_id')
        prev_etf = df_prev[df_prev['ETF'] == etf].set_index('stock_id')
        
        # New Positions
        new_stocks = curr_etf.index.difference(prev_etf.index)
        new_df = curr_etf.loc[new_stocks].copy()
        
        # Exited Positions
        exited_stocks = prev_etf.index.difference(curr_etf.index)
        exit_df = prev_etf.loc[exited_stocks].copy()
        
        # Changed Positions (Weight or Shares)
        common_stocks = curr_etf.index.intersection(prev_etf.index)
        
        curr_common = curr_etf.loc[common_stocks]
        prev_common = prev_etf.loc[common_stocks]
        
        weight_diff = curr_common['weight'] - prev_common['weight']
        shares_diff = curr_common['shares'] - prev_common['shares']
        
        # Filter for non-zero changes (account for float precision)
        # We check if weight changed OR shares changed
        changed_mask = (weight_diff.abs() > 0.001) | (shares_diff.abs() > 0)
        
        changed_df = pd.DataFrame({
            'stock_name': curr_common.loc[changed_mask, 'stock_name'],
            'weight_prev': prev_common.loc[changed_mask, 'weight'],
            'weight_curr': curr_common.loc[changed_mask, 'weight'],
            'weight_diff': weight_diff[changed_mask],
            'shares_prev': prev_common.loc[changed_mask, 'shares'],
            'shares_curr': curr_common.loc[changed_mask, 'shares'],
            'shares_diff': shares_diff[changed_mask]
        })
        
        changes[etf] = {
            'new': new_df,
            'exit': exit_df,
            'changed': changed_df.sort_values(by='weight_diff', ascending=False)
        }
        
    return changes

def generate_html_report(diff_data, date_str):
    """
    Generate a simple HTML report.
    """
    html_content = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <title>主動型 ETF 每日異動報告 - {date_str}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #333; }}
            h2 {{ color: #555; border-bottom: 2px solid #ddd; padding-bottom: 5px; }}
            table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 14px; }}
            th {{ background-color: #f2f2f2; }}
            .increase {{ color: green; }}
            .decrease {{ color: red; }}
            .etf-section {{ margin-bottom: 40px; border: 1px solid #ccc; padding: 20px; border-radius: 5px; }}
            .num {{ text-align: right; }}
        </style>
    </head>
    <body>
        <h1>主動型 ETF 持倉 - 每日異動報告（{date_str}）</h1>
    """
    
    for etf, data in diff_data.items():
        html_content += f"<div class='etf-section'><h2>ETF 代碼：{etf}</h2>"

        # 新增持股
        if not data['new'].empty:
            html_content += "<h3>新增持股</h3><table><thead><tr><th>股票代號</th><th>股票名稱</th><th>股數</th><th>權重 %</th></tr></thead><tbody>"
            for stock_id, row in data['new'].iterrows():
                html_content += f"<tr><td>{stock_id}</td><td>{row['stock_name']}</td><td class='num'>{int(row['shares']):,}</td><td class='num'>{row['weight']}%</td></tr>"
            html_content += "</tbody></table>"
        else:
            html_content += "<p>本日無新增持股。</p>"

        # 移除持股
        if not data['exit'].empty:
            html_content += "<h3>移除持股</h3><table><thead><tr><th>股票代號</th><th>股票名稱</th><th>前期股數</th><th>前期權重 %</th></tr></thead><tbody>"
            for stock_id, row in data['exit'].iterrows():
                html_content += f"<tr><td>{stock_id}</td><td>{row['stock_name']}</td><td class='num'>{int(row['shares']):,}</td><td class='num'>{row['weight']}%</td></tr>"
            html_content += "</tbody></table>"
        else:
            html_content += "<p>本日無移除持股。</p>"

        # 異動持股
        if not data['changed'].empty:
            html_content += "<h3>持倉異動（股數與權重）</h3><table><thead><tr><th>股票代號</th><th>股票名稱</th><th>前期股數</th><th>本期股數</th><th>股數差異</th><th>前期權重</th><th>本期權重</th><th>權重差異</th></tr></thead><tbody>"
            for stock_id, row in data['changed'].iterrows():
                w_diff = row['weight_diff']
                w_color = "increase" if w_diff > 0 else ("decrease" if w_diff < 0 else "")
                w_diff_str = f"{w_diff:+.2f}%"
                
                s_diff = row['shares_diff']
                s_color = "increase" if s_diff > 0 else ("decrease" if s_diff < 0 else "")
                s_diff_str = f"{int(s_diff):+,}"
                
                html_content += f"""
                <tr>
                    <td>{stock_id}</td>
                    <td>{row['stock_name']}</td>
                    <td class='num'>{int(row['shares_prev']):,}</td>
                    <td class='num'>{int(row['shares_curr']):,}</td>
                    <td class='num {s_color}'>{s_diff_str}</td>
                    <td class='num'>{row['weight_prev']}%</td>
                    <td class='num'>{row['weight_curr']}%</td>
                    <td class='num {w_color}'>{w_diff_str}</td>
                </tr>
                """
            html_content += "</tbody></table>"
        else:
            html_content += "<p>本日無顯著異動。</p>"
            
        html_content += "</div>"
        
    html_content += """
    </body>
    </html>
    """
    
    report_file = os.path.join(OUTPUT_DIR, f"report_{date_str}.html")
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
        
    print(f"\n[報告] 已產生 HTML 報告：{report_file}")
    
    # Generate Index Page (for GitHub Pages)
    generate_index_page(date_str)
    
    # Try to open in browser (local only)
    try:
        if os.name == 'nt': # Only on Windows
            os.startfile(report_file)
    except:
        pass

def generate_index_page(latest_date):
    """
    Generate an index.html that redirects or links to the latest report.
    """
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>主動型 ETF 監控 - 最新報告</title>
        <meta http-equiv="refresh" content="0; url=etf_data/report_{latest_date}.html" />
        <style>
            body {{ font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }}
            a {{ text-decoration: none; color: #007bff; font-size: 20px; }}
        </style>
    </head>
    <body>
        <h1>主動型 ETF 監控</h1>
        <p>正在跳轉至最新報告：<a href="etf_data/report_{latest_date}.html">{latest_date}</a></p>
        <p><small>最後更新時間：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</small></p>
    </body>
    </html>
    """
    
    # Index goes in the root directory, not etf_data
    with open("index.html", 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"[資訊] 已更新 index.html，指向 report_{latest_date}.html")

if __name__ == "__main__":
    try:
        monitor_etfs()
    except Exception as e:
        print(f"發生未預期的錯誤：{e}")
        import traceback
        traceback.print_exc()
        input("按 Enter 鍵離開...") # 若直接雙擊執行，保持視窗開啟
