from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import HumanMessage
from app.graph import orvo_app, OrvoState

print("=" * 50)
print("Orvo Agent — Local REPL")
print("Escribí 'salir' para terminar.")
print("=" * 50 + "\n")

state: OrvoState = {
    "messages": [],
    "route": "",
    "needs_human": False,
    "lead_profile": {},
    "hot_lead": False,
    "juan_notified": False,
    "hot_reason": "",
    "phone": "repl_local",
}

while True:
    try:
        mensaje = input("Vos: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nSaliendo.")
        break

    if not mensaje:
        continue
    if mensaje.lower() == "salir":
        break

    state["messages"].append(HumanMessage(content=mensaje))
    state = orvo_app.invoke(state)

    respuesta = state["messages"][-1].content
    route = state.get("route", "?")
    hot = state.get("hot_lead", False)
    profile = state.get("lead_profile", {})

    tag = f"[{route}]"
    if hot:
        tag += " 🔥 LEAD CALIENTE"
    if profile:
        captured = ", ".join(f"{k}={v}" for k, v in profile.items() if v)
        if captured:
            tag += f" | perfil: {captured}"

    print(f"{tag}")
    print(f"Orvo: {respuesta}\n")
