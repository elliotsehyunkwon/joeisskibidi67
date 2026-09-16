import base64
import io
import math
import struct
import wave
import streamlit as st

st.set_page_config(
    page_title="Road to the City",
    page_icon="💵",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
/* Keep the whole game compact enough for one screen */
.block-container {
    max-width: 1250px;
    padding: 0.7rem 1rem 0.2rem !important;
}

div[data-testid="stVerticalBlock"] {
    gap: 0.35rem;
}

h1 {
    margin: 0 !important;
    font-size: 2rem !important;
}

h2, h3 {
    margin: 0.2rem 0 !important;
}

.scene {
    height: 135px !important;
    margin: 0.15rem 0 !important;
}

.game-card, .money-card {
    padding: 0.5rem 0.7rem !important;
}

.money-value {
    font-size: 1.9rem !important;
}

.stage-progress {
    margin: 0.2rem 0 0.35rem !important;
}

div.stButton > button {
    min-height: 48px !important;
}

/* ---------- DOPAMINE CLICK ANIMATION ---------- */

.click-burst {
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 999999;
    animation: screenFlash 0.34s ease-out forwards;
}

.click-burst::before {
    content: "+$";
    position: absolute;
    left: 50%;
    top: 42%;
    transform: translate(-50%, -50%) scale(0.4);

    font-size: 4.2rem;
    font-weight: 1000;
    color: #ffe36b;

    text-shadow:
        0 0 10px #ffbd00,
        0 0 28px #ffbd00,
        0 5px 20px #000;

    animation: cashPop 0.52s cubic-bezier(.2,1.5,.4,1) forwards;
}

.click-burst::after {
    content: "✦  ✦  ✦  ✦  ✦";
    position: absolute;
    left: 50%;
    top: 42%;
    transform: translate(-50%, -50%);

    white-space: nowrap;
    color: #fff2a3;
    font-size: 1.8rem;
    letter-spacing: 0.45rem;

    animation: sparkPop 0.48s ease-out forwards;
}

@keyframes cashPop {
    0% {
        opacity: 0;
        transform: translate(-50%, -50%) scale(0.35);
    }

    20% {
        opacity: 1;
        transform: translate(-50%, -50%) scale(1.18);
    }

    55% {
        opacity: 1;
        transform: translate(-50%, -70%) scale(1);
    }

    100% {
        opacity: 0;
        transform: translate(-50%, -125%) scale(0.85);
    }
}

@keyframes sparkPop {
    0% {
        opacity: 0;
        transform: translate(-50%, -50%) scale(0.3) rotate(0deg);
    }

    35% {
        opacity: 1;
        transform: translate(-50%, -50%) scale(1.15) rotate(8deg);
    }

    100% {
        opacity: 0;
        transform: translate(-50%, -80%) scale(1.7) rotate(-8deg);
    }
}

@keyframes screenFlash {
    0% {
        background: rgba(255,216,77,0.16);
    }

    100% {
        background: rgba(255,216,77,0);
    }
}

footer {
    visibility: hidden;
}
</style>
""", unsafe_allow_html=True)


# -----------------------------
# Game data
# -----------------------------
STAGES = [
    {
        "name": "Countryside",
        "goal": 1_000,
        "description": "Escape the countryside and reach the city.",
        "emoji": "🌾",
        "class": "countryside",
    },
    {
        "name": "Streets",
        "goal": 5_000,
        "description": "Make enough money to escape the streets.",
        "emoji": "🚶",
        "class": "sidewalk",
    },
    {
        "name": "Half-Basement House",
        "goal": 50_000,
        "description": "Climb out of the half-basement and keep moving up.",
        "emoji": "🏠",
        "class": "basement",
    },
    {
        "name": "First Floor",
        "goal": 250_000,
        "description": "Save enough to leave the first-floor apartment.",
        "emoji": "🪟",
        "class": "firstfloor",
    },
    {
        "name": "Regional City",
        "goal": 1_250_000,
        "description": "Reach the final apartment and complete the journey.",
        "emoji": "🏙️",
        "class": "city",
    },
]

if "money" not in st.session_state:
    st.session_state.money = 0.0
if "click_value" not in st.session_state:
    st.session_state.click_value = 1.0
if "click_upgrade_level" not in st.session_state:
    st.session_state.click_upgrade_level = 0
if "extra_clicks" not in st.session_state:
    st.session_state.extra_clicks = 0
if "click_count" not in st.session_state:
    st.session_state.click_count = 0
if "stage" not in st.session_state:
    st.session_state.stage = 0
if "message" not in st.session_state:
    st.session_state.message = "Start clicking to earn money."
if "show_click_animation" not in st.session_state:
    st.session_state.show_click_animation = False

def fmt_money(value):
    if value >= 1_000_000:
        return f"${value/1_000_000:.2f}M"
    if value >= 1_000:
        return f"${value:,.0f}"
    return f"${value:,.0f}"

def upgrade_cost(level):
    # Starts at $1 and increases by 50% each purchase.
    return max(1, math.ceil(1 * (1.5 ** level)))

def make_register_sound():
    """Small synthesized cash-register 'ding' so no external audio asset is required."""
    sample_rate = 22050
    duration = 0.20
    frames = []
    for i in range(int(sample_rate * duration)):
        t = i / sample_rate
        env = math.exp(-18 * t)
        sample = (
            0.48 * math.sin(2 * math.pi * 880 * t)
            + 0.28 * math.sin(2 * math.pi * 1320 * t)
            + 0.16 * math.sin(2 * math.pi * 1760 * t)
        ) * env
        frames.append(int(max(-1, min(1, sample)) * 32767))
    raw = b"".join(struct.pack("<h", x) for x in frames)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(raw)
    return base64.b64encode(buffer.getvalue()).decode()

REGISTER_SOUND = make_register_sound()

# -----------------------------
# Styling
# -----------------------------
st.markdown(
    """
<style>
    .stApp {
        background: #171717;
    }
    .block-container {
        max-width: 1150px;
        padding-top: 1rem;
        padding-bottom: 2rem;
    }
    .game-shell {
        background: #252525;
        border: 3px solid #0d0d0d;
        border-radius: 18px;
        box-shadow: 0 8px 0 #0b0b0b;
        padding: 16px;
    }
    .title {
        font-size: 2.25rem;
        font-weight: 900;
        text-align: center;
        color: #ffd84d;
        text-shadow: 3px 3px #111;
        margin-bottom: 0.15rem;
    }
    .subtitle {
        text-align: center;
        color: #dddddd;
        margin-bottom: 1rem;
    }
    .scene {
        min-height: 360px;
        border-radius: 16px;
        border: 4px solid #111;
        position: relative;
        overflow: hidden;
        display: flex;
        align-items: flex-end;
        justify-content: center;
        padding: 20px;
        box-shadow: inset 0 -80px 0 rgba(0,0,0,.18);
    }
    .scene.countryside {
        background:
            linear-gradient(#80c8ef 0 52%, #6fa84f 52% 73%, #4b873c 73%);
    }
    .scene.sidewalk {
        background:
            linear-gradient(#a8d6ed 0 44%, #777 44% 65%, #414141 65%);
    }
    .scene.basement {
        background:
            linear-gradient(#c6bcae 0 58%, #7c7165 58% 100%);
    }
    .scene.firstfloor {
        background:
            linear-gradient(#d9e5ef 0 60%, #b7a68d 60% 100%);
    }
    .scene.city {
        background:
            linear-gradient(#758da3 0 48%, #5a6065 48% 100%);
    }
    .character {
        width: 150px;
        height: 190px;
        border-radius: 55px 55px 28px 28px;
        background: #d9a06f;
        border: 5px solid #181818;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        box-shadow: 0 8px 0 rgba(0,0,0,.35);
        user-select: none;
    }
    .character .face { font-size: 64px; }
    .character .bag { font-size: 34px; margin-top: -3px; }
    .scene-label {
        position: absolute;
        top: 12px;
        left: 14px;
        background: rgba(0,0,0,.65);
        color: white;
        border: 2px solid #111;
        border-radius: 9px;
        padding: 6px 12px;
        font-weight: 800;
    }
    .money-card {
        background: #151515;
        border: 3px solid #050505;
        border-radius: 13px;
        padding: 13px;
        text-align: center;
        margin: 8px 0;
    }
    .money-label {
        color: #aaa;
        font-size: .85rem;
        text-transform: uppercase;
        letter-spacing: .08em;
    }
    .money-value {
        color: #ffd84d;
        font-size: 2.25rem;
        font-weight: 900;
    }
    .goal {
        color: #e8e8e8;
        font-weight: 700;
        text-align: center;
    }
    .shop-card {
        background: #303030;
        border: 3px solid #121212;
        border-radius: 14px;
        padding: 13px;
        margin: 7px 0;
    }
    .shop-title {
        font-size: 1.1rem;
        font-weight: 900;
        color: #fff;
    }
    .shop-desc {
        color: #bdbdbd;
        font-size: .88rem;
    }
    .tiny {
        color: #9e9e9e;
        font-size: .78rem;
    }
    div.stButton > button {
        border: 3px solid #111 !important;
        border-radius: 12px !important;
        font-weight: 900 !important;
        min-height: 48px !important;
        background: #f0b51b !important;
        color: #171717 !important;
        box-shadow: 0 4px 0 #111 !important;
    }
    div.stButton > button:hover {
        transform: translateY(1px);
        box-shadow: 0 3px 0 #111 !important;
    }
    .click-button button {
        min-height: 110px !important;
        font-size: 1.55rem !important;
        background: #ffd84d !important;
    }
    .progress-wrap {
        background: #101010;
        border: 3px solid #080808;
        border-radius: 12px;
        overflow: hidden;
        height: 30px;
        margin: 8px 0 14px;
    }
    .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #e8a400, #ffe071);
        color: #171717;
        font-weight: 900;
        text-align: center;
        line-height: 24px;
    }
</style>
""",
    unsafe_allow_html=True,
)

stage = STAGES[st.session_state.stage]
goal = stage["goal"]
progress = min(100, st.session_state.money / goal * 100)

# -----------------------------
# Header
# -----------------------------
st.markdown('<div class="game-shell">', unsafe_allow_html=True)
st.markdown('<div class="title">ROAD TO THE CITY</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">A five-stage clicker RPG inspired by classic beggar-style progression.</div>',
    unsafe_allow_html=True,
)

left, middle, right = st.columns([1.2, 1.8, 1.2])
with left:
    st.markdown(
        f'<div class="money-card"><div class="money-label">Cash</div>'
        f'<div class="money-value">{fmt_money(st.session_state.money)}</div></div>',
        unsafe_allow_html=True,
    )
with middle:
    st.markdown(
        f'<div class="money-card"><div class="money-label">Stage {st.session_state.stage + 1} / 5</div>'
        f'<div class="money-value">{stage["emoji"]} {stage["name"]}</div></div>',
        unsafe_allow_html=True,
    )
with right:
    st.markdown(
        f'<div class="money-card"><div class="money-label">Per Click</div>'
        f'<div class="money-value">${st.session_state.click_value:.0f}</div></div>',
        unsafe_allow_html=True,
    )

st.markdown(
    f"""
    <div class="goal">{stage["description"]} &nbsp; Target: {fmt_money(goal)}</div>
    <div class="progress-wrap">
        <div class="progress-fill" style="width:{max(progress, 2)}%">
            {progress:.1f}%
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# Main play area
# -----------------------------
play_col, shop_col = st.columns([1.55, 1], gap="large")

with play_col:
    st.markdown(
        f"""
        <div class="scene {stage['class']}">
            <div class="scene-label">Stage {st.session_state.stage + 1}: {stage['name']}</div>
            <div class="character">
                <div class="face">🧑</div>
                <div class="bag">💰</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="click-button">', unsafe_allow_html=True)
    if st.button(
    "💰 CLICK  +$" + str(
        st.session_state.click_value *
        (1 + st.session_state.extra_clicks)
    ),
    use_container_width=True
):
    gain = st.session_state.click_value * (
        1 + st.session_state.extra_clicks
    )

    st.session_state.money += gain
    st.session_state.click_count += 1
    st.session_state.message = f"+${gain:,}"

    # Trigger dopamine animation
    st.session_state.show_click_animation = True

    # Cash register sound
    st.markdown(
        f"""
        <audio autoplay>
            <source
                src="data:audio/wav;base64,{SOUND_B64}"
                type="audio/wav"
            >
        </audio>
        """,
        unsafe_allow_html=True
    )

    st.rerun()


# Display animation after clicking
if st.session_state.get("show_click_animation", False):

    st.markdown(
        '<div class="click-burst"></div>',
        unsafe_allow_html=True
    )

    # Only show it once
    st.session_state.show_click_animation = False
    st.info(
        f"{st.session_state.message}  •  Clicks: {st.session_state.click_count:,}  •  "
        f"Click multiplier: x{1 + st.session_state.extra_clicks}"
    )

    if st.session_state.money >= goal:
        if st.session_state.stage < len(STAGES) - 1:
            if st.button(
                f"🚪 ESCAPE STAGE → {STAGES[st.session_state.stage + 1]['name']}",
                use_container_width=True,
                key="escape",
            ):
                st.session_state.stage += 1
                st.session_state.message = f"You escaped! Welcome to {STAGES[st.session_state.stage]['name']}."
                st.rerun()
        else:
            st.success("🏆 YOU ESCAPED THE REGIONAL CITY! You completed all 5 stages.")
            if st.button("🔄 Start Again", use_container_width=True, key="restart"):
                for key, value in {
                    "money": 0.0,
                    "click_value": 1.0,
                    "click_upgrade_level": 0,
                    "extra_clicks": 0,
                    "click_count": 0,
                    "stage": 0,
                    "message": "Start clicking to earn money.",
                }.items():
                    st.session_state[key] = value
                st.rerun()

with shop_col:
    st.markdown("## 🛒 SHOP")
    st.caption("Upgrade your earning power. Costs rise by 50% after every purchase.")

    cost_a = upgrade_cost(st.session_state.click_upgrade_level)
    st.markdown(
        f"""
        <div class="shop-card">
            <div class="shop-title">💵 +$1 Per Click</div>
            <div class="shop-desc">Increase the base payout of every click by $1.</div>
            <div class="tiny">Level {st.session_state.click_upgrade_level} • Next cost: ${cost_a:,}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button(f"BUY +$1 CLICK  —  ${cost_a:,}", use_container_width=True, key="upgrade_money"):
        if st.session_state.money >= cost_a:
            st.session_state.money -= cost_a
            st.session_state.click_value += 1
            st.session_state.click_upgrade_level += 1
            st.session_state.message = "Upgrade purchased: +$1 per click."
            st.rerun()
        else:
            st.warning("Not enough cash.")

    cost_b = upgrade_cost(st.session_state.extra_clicks)
    st.markdown(
        f"""
        <div class="shop-card">
            <div class="shop-title">⚡ +1 Click Per Click</div>
            <div class="shop-desc">Each press counts as one additional click, multiplying the payout.</div>
            <div class="tiny">Level {st.session_state.extra_clicks} • Next cost: ${cost_b:,}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button(f"BUY +1 CLICK  —  ${cost_b:,}", use_container_width=True, key="upgrade_clicks"):
        if st.session_state.money >= cost_b:
            st.session_state.money -= cost_b
            st.session_state.extra_clicks += 1
            st.session_state.message = "Upgrade purchased: +1 click per press."
            st.rerun()
        else:
            st.warning("Not enough cash.")

    st.markdown("---")
    st.markdown("### 🗺️ STAGES")
    for i, s in enumerate(STAGES):
        status = "✅" if i < st.session_state.stage else ("▶️" if i == st.session_state.stage else "🔒")
        st.write(f"{status} **{i+1}. {s['name']}** — {fmt_money(s['goal'])}")

st.markdown("</div>", unsafe_allow_html=True)

st.caption(
    "Progress is kept for the current browser session. For persistent saves, add a database or file-backed save system later."
)
