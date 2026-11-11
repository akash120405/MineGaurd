"""Make one minimal real request to each configured provider; print no secrets."""
import asyncio
from dotenv import load_dotenv
load_dotenv()
from app.providers import call_provider,ProviderError

async def main():
    for name in ('groq','gemini'):
        try:
            result=await call_provider(name,'Return JSON with an empty claims array.','Connectivity test. Return {"claims":[]}')
            print(name+': connected, valid JSON response')
        except ProviderError as e:
            print(str(e))

if __name__=='__main__':asyncio.run(main())
