import json
import re
from fastapi import FastAPI, Request
import uvicorn

app = FastAPI()

MOCK_DATA = {
    "source_analysis": {
        "summary": "这是一个关于反抗命运的宏大史诗。",
        "coreConflict": "人与神的博弈，自由与枷锁的对抗。",
        "themes": ["自由", "反抗", "牺牲"],
        "emotionArc": ["压抑", "觉醒", "爆发"],
        "motifs": ["火", "锁链", "莲花"],
        "audienceLens": "追求热血与感动的青年群体",
        "lyricFocus": "聚焦于打破陈规的勇气。"
    },
    "lyric_plan": {
        "concept": "打破枷锁的狂想曲",
        "narrativePOV": "第一人称",
        "sections": [
            {"name": "主歌", "purpose": "铺垫压抑气氛", "emotionalBeat": "沉重", "imagery": ["深渊中的微光", "沉重的铁链"]},
            {"name": "副歌", "purpose": "情感彻底爆发", "emotionalBeat": "高亢", "imagery": ["冲破云霄的烈焰", "破碎的枷锁"]}
        ],
        "hook": "我命由我不由天",
        "keyLines": ["生而为魔，那又如何？", "若命运不公，就和它斗到底！"],
        "chorusDraft": ["燃尽这残躯，也要换取那一瞬的自由", "逆天而行，才是我的宿命"],
        "languageStyle": "豪迈且充满力量感",
        "forComposition": "建议加入重金属元素或宏大的弦乐背景。"
    },
    "composition_brief": {
        "titleProposal": "哪吒·觉醒",
        "tempo": "128 BPM",
        "key": "G Major",
        "timeSignature": "4/4",
        "arrangement": ["强力电吉他", "激昂定音鼓", "宏大交响乐"],
        "vocalDirection": "主歌低沉有力，副歌充满张力与穿透力。",
        "sectionDynamics": [
            {"section": "Intro", "dynamic": "Pianissimo (极弱)"},
            {"section": "Chorus", "dynamic": "Fortissimo (极强)"}
        ],
        "mixMood": "史诗般壮丽"
    },
    "cover_direction": {
        "coverTitle": "哪吒：命运之战",
        "visualConcept": "火海中屹立的不屈身影",
        "composition": "中心构图，低仰角拍摄",
        "palette": ["深红", "金黄", "墨黑"],
        "subjectFocus": "角色坚毅的眼神",
        "negativeSpace": "四周的灰烬与烟尘",
        "renderPrompt": "epic cinematic poster, nezha standing in fire, rebellious eyes, hyper-realistic, 8k",
        "avoid": ["卡通感", "柔和色彩"]
    },
    "audio_render": {
        "versionTitle": "哪吒：不屈意志（终稿）",
        "performanceDirection": "唱出那种即便面对毁灭也要奋力一搏的决绝。",
        "instrumentation": ["电声乐队", "全编制管弦乐"],
        "chorusLift": "副歌通过升调和增加打击乐器来提升情感张力。",
        "introDirection": "以微弱的单簧管独奏开始。",
        "endingDirection": "在宏大的合唱中戛然而止。",
        "productionNotes": ["注重低音的厚重感", "人声需要适度的失真处理以增加质感"],
        "renderPrompt": "epic orchestral rock, cinematic vocal, powerful and raw"
    }
}

@app.post("/api/mock")
async def mock_endpoint(request: Request):
    body = await request.json()
    content = ""
    if "messages" in body:
        content = body["messages"][0]["content"]
    else:
        content = body.get("prompt", "")

    # Use more robust matching
    stage = "source_analysis"
    if "歌词结构节点" in content or "lyric_plan" in content:
        stage = "lyric_plan"
    elif "编曲设定节点" in content or "composition_brief" in content:
        stage = "composition_brief"
    elif "封面方向节点" in content or "cover_direction" in content:
        stage = "cover_direction"
    elif "音频导演节点" in content or "audio_render" in content:
        stage = "audio_render"
    elif "剧情提炼节点" in content or "source_analysis" in content:
        stage = "source_analysis"

    print(f"MOCK API: Received request for stage: {stage}")

    mock_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": f"<WORKFLOW_JSON>\n{json.dumps(MOCK_DATA[stage], ensure_ascii=False, indent=2)}\n</WORKFLOW_JSON>"
                }
            }
        ]
    }
    return mock_response

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8099)
