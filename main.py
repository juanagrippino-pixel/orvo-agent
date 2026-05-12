from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import HumanMessage
from app.graph import orvo_app, OrvoState

print("=" * 50)
print("Orvo Agent — Local REPL")
print("Escribí 'salir' para terminar.")
print("=" * 50 + "\n")

state: OrvoState = {"messages": [], "route": "", "needs_human": False}

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
    needs_human = state.get("needs_human", False)

    tag = f"[{route}]"
    if needs_human:
        tag += " ⚠ HUMAN NEEDED"

    print(f"{tag}")
    print(f"Orvo: {respuesta}\n")
