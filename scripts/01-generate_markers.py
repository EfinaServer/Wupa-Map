"""
Created by yxetal
Modified to inject directly into overworld.conf
"""
import argparse
import json
import os
import re
from urllib.parse import urlparse
from urllib.request import urlopen

# --- Configuration ---
HEIGHT_Y = 80
DEFAULT_OUTPUT_FILE = "config/maps/overworld.conf" # 改為直接指向 overworld.conf
DEFAULT_STATION_URI = "https://wupa.ydtw.net/api/stations"
DEFAULT_LINE_URI = "https://wupa.ydtw.net/api/lines"
DEFAULT_RIVER_URI = "https://wupa.ydtw.net/api/rivers"
INDENT = "\t" # Use Tab for indentation

# --- Color Mapping ---
COLOR_MAP = {
	"red":        {"r": 255, "g": 0,   "b": 0,   "a": 1.0},
	"orange":     {"r": 255, "g": 165, "b": 0,   "a": 1.0},
	"purple":     {"r": 128, "g": 0,   "b": 128, "a": 1.0},
	"green":      {"r": 0,   "g": 128, "b": 0,   "a": 1.0},
	"brown":      {"r": 165, "g": 42,  "b": 42,  "a": 1.0},
	"blue":       {"r": 0,   "g": 0,   "b": 255, "a": 1.0},
	"yellow":     {"r": 255, "g": 255, "b": 0,   "a": 1.0},
	"DodgerBlue": {"r": 30,  "g": 144, "b": 255, "a": 1.0},
	"LightGray":  {"r": 211, "g": 211, "b": 211, "a": 1.0},
	"default":    {"r": 255, "g": 255, "b": 255, "a": 1.0}
}

# --- HOCON Writer Helper ---
def escape_hocon_string(s):
	"""Escape special characters for HOCON string values."""
	s = s.replace("\\", "\\\\")
	s = s.replace('"', '\\"')
	s = s.replace("\n", "\\n")
	s = s.replace("\r", "\\r")
	s = s.replace("\t", "\\t")
	return s

def to_hocon(obj, level=0):
	"""Recursively converts Python objects to HOCON-formatted string."""
	indent_str = INDENT * level
	next_indent = INDENT * (level + 1)

	if isinstance(obj, dict):
		lines = []
		if level > 0: lines.append("{")
		for key, value in obj.items():
			k_str = key if key.replace("-", "").replace("_", "").isalnum() else f'"{escape_hocon_string(key)}"'
			val_str = to_hocon(value, level + 1).lstrip()
			lines.append(f"{next_indent}{k_str}: {val_str}")

		if level > 0:
			lines.append(f"{indent_str}}}")
			return "\n".join(lines)
		else:
			return "\n".join(lines)

	elif isinstance(obj, list):
		is_simple_points = len(obj) > 0 and isinstance(obj[0], dict) and "x" in obj[0]
		if is_simple_points:
			lines = ["["]
			for item in obj:
				props = [f"{k}: {v}" for k, v in item.items()]
				lines.append(f"{next_indent}{{ {', '.join(props)} }}")
			lines.append(f"{indent_str}]")
			return "\n".join(lines)
		else:
			return json.dumps(obj)

	elif isinstance(obj, str):
		return f'"{escape_hocon_string(obj)}"'
	elif isinstance(obj, bool):
		return str(obj).lower()
	else:
		return str(obj)

def load_json(uri):
	parsed = urlparse(uri)
	if parsed.scheme in {"http", "https"}:
		try:
			with urlopen(uri, timeout=30) as resp:
				data = resp.read().decode("utf-8")
				return json.loads(data)
		except Exception as exc:
			print(f"⚠️ Failed to download {uri}: {exc}")
			return []

	if not os.path.exists(uri):
		print(f"⚠️ {uri} not found.")
		return []
	with open(uri, 'r', encoding='utf-8') as f:
		return json.load(f)

# --- Config Injector ---
def inject_hocon_block(file_content, key_name, new_block_str):
	"""Finds a top-level block like 'key_name: { ... }' and replaces it."""
	# 尋找目標 key (例如 marker-sets:) 以及它後面的第一個左大括號 '{'
	pattern = re.compile(rf"{key_name}\s*:\s*\{{")
	match = pattern.search(file_content)
	
	if not match:
		# 如果找不到 marker-sets，就直接加在檔案最下面
		print(f"⚠️ Could not find '{key_name}: {{' in config. Appending to end.")
		return file_content.rstrip() + "\n\n" + new_block_str + "\n"

	start_idx = match.end() - 1  # '{' 的位置
	open_braces = 0
	end_idx = -1

	# 括號匹配邏輯，找出這個區塊在哪裡結束
	for i in range(start_idx, len(file_content)):
		if file_content[i] == '{':
			open_braces += 1
		elif file_content[i] == '}':
			open_braces -= 1
			if open_braces == 0:
				end_idx = i
				break

	if end_idx != -1:
		# 將舊的區塊替換為我們新生成的區塊
		return file_content[:match.start()] + new_block_str + file_content[end_idx+1:]
	else:
		print("⚠️ Error: Unmatched braces found in config file. Aborting injection.")
		return file_content

def parse_args():
	parser = argparse.ArgumentParser(description="Inject BlueMap markers from JSON sources into config.")
	parser.add_argument(
		"-o",
		"--output",
		default=DEFAULT_OUTPUT_FILE,
		help="Target HOCON file path (default: config/maps/overworld.conf)",
	)
	parser.add_argument(
		"--station-uri",
		default=DEFAULT_STATION_URI,
		help="Path or URI to station JSON",
	)
	parser.add_argument(
		"--line-uri",
		default=DEFAULT_LINE_URI,
		help="Path or URI to line JSON",
	)
	parser.add_argument(
		"--river-uri",
		default=DEFAULT_RIVER_URI,
		help="Path or URI to river JSON",
	)
	return parser.parse_args()


def main(output_file, station_uri, line_uri, river_uri):
	stations = load_json(station_uri)
	lines = load_json(line_uri)
	rivers = load_json(river_uri)

	marker_sets = {}

	# 1. Stations
	if stations:
		markers = {}
		for s in stations:
			markers[s['id']] = {
				"type": "poi",
				"label": s['name'],
				"position": {"x": s['x'], "y": HEIGHT_Y, "z": s['y']},
				"icon": "assets/poi.svg",
				"anchor": {"x": 25, "y": 45},
				"sorting": 0,
				"listed": True,
				"min-distance": 10,
				"max-distance": 10000000
			}
		marker_sets["stations"] = {
			"label": "Metro Stations",
			"toggleable": True,
			"default-hidden": False,
			"markers": markers
		}

	# 2. Lines
	if lines:
		markers = {}
		for l in lines:
			path = [{"x": p['x'], "y": HEIGHT_Y, "z": p['y']} for p in l['points']]
			color = COLOR_MAP.get(l.get('color'), COLOR_MAP['default'])
			markers[l['id']] = {
				"type": "line",
				"label": l['name'],
				"line": path,
				"detail": f"{l['name']} (ID: {l['id']})",
				"depth-test": False,
				"line-width": l.get('width', 5),
				"line-color": color,
				"sorting": 0,
				"listed": True,
				"min-distance": 10,
				"max-distance": 10000000
			}
		marker_sets["lines"] = {
			"label": "Metro Lines",
			"toggleable": True,
			"markers": markers
		}

	# 3. Rivers
	if rivers:
		markers = {}
		for r in rivers:
			path = [{"x": p['x'], "y": HEIGHT_Y - 1, "z": p['y']} for p in r['points']]
			markers[r['id']] = {
				"type": "line",
				"label": r['name'],
				"line": path,
				"depth-test": False,
				"line-width": r.get('width', 10),
				"line-color": {"r": 0, "g": 255, "b": 255, "a": 0.8},
				"sorting": 0,
				"listed": True,
				"min-distance": 10,
				"max-distance": 10000000
			}
		marker_sets["rivers"] = {
			"label": "Rivers",
			"toggleable": True,
			"markers": markers
		}

	# 產生新的 marker-sets HOCON 字串
	new_marker_hocon = to_hocon({"marker-sets": marker_sets})

	# 讀取並修改原本的 overworld.conf
	if os.path.exists(output_file):
		with open(output_file, 'r', encoding='utf-8') as f:
			original_content = f.read()
		
		# 將新的 marker-sets 注入到原本的內容中
		updated_content = inject_hocon_block(original_content, "marker-sets", new_marker_hocon)
		
		with open(output_file, 'w', encoding='utf-8') as f:
			f.write(updated_content)
		
		print(f"✅ Successfully injected markers into {output_file}.")
	else:
		# 如果檔案不存在，則建立一個新的 (防呆機制)
		os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
		with open(output_file, 'w', encoding='utf-8') as f:
			f.write("# BlueMap Config\n")
			f.write(new_marker_hocon)
		print(f"⚠️ {output_file} did not exist. Created a new one with markers.")

if __name__ == "__main__":
	args = parse_args()
	main(
		output_file=args.output,
		station_uri=args.station_uri,
		line_uri=args.line_uri,
		river_uri=args.river_uri,
	)