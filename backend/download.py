import os
import json
import httpx
import asyncio
import aiofiles
import pandas as pd
from io import StringIO
from datetime import datetime

# 配置常量
CONFIG_FILE = "ARK_URL.json"
BASE_DATA_DIR = "./raw_data"

async def download_and_save_fund(client: httpx.AsyncClient, fund_name: str, url: str):
    """异步下载单个基金并按日期保存"""
    print(f"🔍 [CypherInvest] 正在检查 {fund_name}...")
    
    # 模拟 User-Agent 防止被拦截
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    try:
        # 1. 发起 GET 请求下载 CSV
        response = await client.get(url, headers=headers, timeout=60.0, follow_redirects=True)
        if response.status_code != 200:
            print(f"❌ {fund_name}: 请求失败 (HTTP {response.status_code})")
            return

        # 2. 解析 CSV 内部日期 (这是最准确的文件日期)
        # 注意：ARK CSV 内部日期格式通常是 MM/DD/YYYY
        df = pd.read_csv(StringIO(response.text))
        if df.empty or 'date' not in df.columns:
            print(f"❌ {fund_name}: CSV 内部找不到日期，跳过。")
            return
            
        # 提取第一行日期，例如 "03/25/2026"
        raw_date_str = str(df['date'].iloc[0]).strip()
        
        # 3. 转换为标准文件名日期 2026-03-25
        file_date = datetime.strptime(raw_date_str, '%m/%d/%Y').date()
        clean_date = file_date.strftime('%Y-%m-%d')

        # 4. 创建基金子文件夹 (例如: ./raw_data/ARKK)
        fund_dir = os.path.join(BASE_DATA_DIR, fund_name.upper())
        os.makedirs(fund_dir, exist_ok=True)

        # 5. 生成带日期的文件名 (例如: 2026-03-25_ARKK.csv)
        file_name = f"{clean_date}_{fund_name.upper()}.csv"
        file_path = os.path.join(fund_dir, file_name)

        # 6. 如果文件已存在，则跳过下载 (避免重复请求官网)
        if os.path.exists(file_path):
            print(f"😴 {fund_name}: {clean_date} 的数据已存在，跳过。")
            return

        # 7. 异步保存文件内容
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(response.text)
        print(f"✅ {fund_name}: 成功保存 {clean_date} 数据 -> {file_path}")

    except Exception as e:
        print(f"⚠️ {fund_name}: 发生未知错误 - {e}")

async def main():
    """CypherInvest 数据抓取引擎入口"""
    print(f"🏁 [CypherInvest] 开始同步 ARK 所有基金持仓... {datetime.now().strftime('%H:%M:%S')}")
    
    # 初始化根目录
    os.makedirs(BASE_DATA_DIR, exist_ok=True)

    # 1. 读取 JSON 配置文件
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            fund_urls = json.load(f)
    except FileNotFoundError:
        print(f"❌ 找不到配置文件 {CONFIG_FILE}")
        return

    # 2. 创建一个全局异步客户端 (为了重用连接，效率更高)
    async with httpx.AsyncClient() as client:
        # 创建并发任务列表
        tasks = []
        for fund_name, url in fund_urls.items():
            # 创建异步任务对象
            task = download_and_save_fund(client, fund_name, url)
            tasks.append(task)
        
        # 3. 并发执行所有任务，并等待全部完成
        await asyncio.gather(*tasks)

    print(f"🏁 [CypherInvest] 所有基金数据同步完成。 {datetime.now().strftime('%H:%M:%S')}")

if __name__ == "__main__":
    # 需要先执行 pip3 install httpx pandas aiofiles 
    asyncio.run(main())