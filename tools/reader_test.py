"""Cold-reader test: give an article (or only its opening) to several chat models
playing a tired contest judge. Weak signal only; AI is not the real judge.
Usage: python tools/reader_test.py ARTICLE.md TAG   (key read from $SILICONFLOW_API_KEY)
Raw outputs go to docs/reader_test/<TAG>_<mode>_<model>.txt"""
import os, re, sys, json, pathlib, concurrent.futures as cf
import httpx

MODELS = [
    ("qwen3.6-35b-a3b", "Qwen/Qwen3.6-35B-A3B", {"enable_thinking": False}),
    ("deepseek-v4-flash", "deepseek-ai/DeepSeek-V4-Flash", {}),
    ("glm-4.5-air", "zai-org/GLM-4.5-Air", {"enable_thinking": False}),
]
PERSONA = ("You are a tired judge for a DEV.to coding contest. You have about 3 minutes per post and "
           "60 posts to score tonight. You are not a compiler: you skim, you use your own plain vocabulary, "
           "and you will only sign a score if you feel you understood the post and can trust it. ")
Q_OPEN = ("Below is the title and the first screen of one submission. Answer briefly and honestly, as that judge:\n"
          "(a) In two sentences, retell what happened.\n(b) Who is this for?\n"
          "(c) Would you keep reading? Why or why not?\n(d) What is confusing or off-putting?\n\n")
Q_FULL = ("Below is one full submission. The contest criteria, in order of weight: Writing Quality (most), "
          "relevance to the theme 'Build for a Friend', creativity, technical execution. "
          "Give a 1-10 score for each of the four, then the top 3 weaknesses. Be candid, do not flatter.\n\n")

def parts(text):
    m = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
    fm, body = m.group(1), m.group(2)
    title = re.search(r'^title:\s*"?(.*?)"?\s*$', fm, re.M).group(1)
    return title, body.strip()

def opening(body):
    head, rest = body.split("## What I Built", 1)
    first_par = rest.strip().split("\n\n")[0]
    return head.strip() + "\n\n## What I Built\n\n" + first_par

def call(model, extra, prompt):
    r = httpx.post("https://api.siliconflow.cn/v1/chat/completions",
        headers={"Authorization": "Bearer " + os.environ["SILICONFLOW_API_KEY"]},
        json={"model": model, "messages": [{"role": "system", "content": PERSONA}, {"role": "user", "content": prompt}],
              "temperature": 0.3, "max_tokens": 3000, **extra}, timeout=240)
    r.raise_for_status()
    return r.json()["choices"][0]["message"].get("content") or ""

def main():
    src, tag = sys.argv[1], sys.argv[2]
    title, body = parts(pathlib.Path(src).read_text())
    out = pathlib.Path("docs/reader_test"); out.mkdir(parents=True, exist_ok=True)
    jobs = []
    for mode, q, text in (("open", Q_OPEN, opening(body)), ("full", Q_FULL, body)):
        for name, model, extra in MODELS:
            jobs.append((mode, name, model, extra, q + "TITLE: " + title + "\n\n" + text))
    def run(j):
        mode, name, model, extra, prompt = j
        try: res = call(model, extra, prompt)
        except Exception as e: res = f"ERROR: {type(e).__name__}: {str(e)[:200]}"
        (out / f"{tag}_{mode}_{name}.txt").write_text(f"model: {model}\nmode: {mode}\n\n{res}\n")
        return mode, name, len(res)
    with cf.ThreadPoolExecutor(6) as ex:
        for r in ex.map(run, jobs): print(r)
main()
