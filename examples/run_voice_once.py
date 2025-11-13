import asyncio
from graph.runtime import NPCGraph

async def main():
    npc = NPCGraph()
    out = await npc.respond_once(
        "Lyra, o que acha de atravessar agora?",
        events=[{"source":"GM","type":"rumor","content":"Pedágio na Ponte do Carvalho."}],
    )
    print("THREAD:", out["thread_id"]) 
    print("REPLY:", out["reply_text"])  # envie para TTS

if __name__ == "__main__":
    asyncio.run(main())