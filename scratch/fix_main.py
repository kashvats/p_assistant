with open("src/living_assistant/webui/src/main.js", encoding="utf-8") as f:
    src = f.read()
idx = src.find("const NAV = [")
end = src.find("];", idx) + 2
print(repr(src[idx:end]))
