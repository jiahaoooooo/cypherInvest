import os
import httpx
import asyncio

async def get_logo_url(ticker):
    ticker = ticker.upper()
    
    # 1. 优先查本地映射 (速度最快)
    mapping = {
        "TSLA": "tesla.com",
        "COIN": "coinbase.com",
        "SQ": "block.xyz",
        "PLTR": "palantir.com"
    }
    
    domain = mapping.get(ticker)
    
    # 2. 如果映射表没有，尝试“暴力拼接” (成功率 80%)
    if not domain:
        domain = f"{ticker.lower()}.com"
        
    logo_url = f"https://logo.clearbit.com/{domain}"
    
    # 3. 验证图片是否真的存在
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.head(logo_url)
            if resp.status_code == 200:
                return logo_url
            else:
                # 4. 兜底方案：用简单的字母占位图
                return f"https://ui-avatars.com/api/?name={ticker}&background=0ea5e9&color=fff"
        except:
            return f"https://ui-avatars.com/api/?name={ticker}"

async def download_all_logos(tickers):
    for ticker in tickers:
        url = await get_logo_url(ticker)
        print(f"🎯 {ticker} -> {url}")
        # 这里你可以加上保存到本地 assets/logos/{ticker}.png 的代码
        await asyncio.sleep(0.5) # 稍微歇会儿，对服务器温柔点

if __name__ == "__main__":
    asyncio.run(download_all_logos(['TSLA', 'COIN', 'ROKU', 'PLTR', 'AAPL']))