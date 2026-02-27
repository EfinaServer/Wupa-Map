"""
Created by yxetal
"""
import argparse
import json
import os
from urllib.parse import urlparse
from urllib.request import urlopen

# --- Configuration ---
HEIGHT_Y = 80
DEFAULT_OUTPUT_FILE = "config/maps/overworld_markers.conf"
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
			# Don't quote keys if they are safe identifiers
			k_str = key if key.replace("-", "").replace("_", "").isalnum() else f'"{escape_hocon_string(key)}"'
			# Format: key: value
			val_str = to_hocon(value, level + 1).lstrip()
			# If value is a block (ends with }), we don't need a trailing comma implicitly in HOCON,
			# but putting keys on new lines is key.
			lines.append(f"{next_indent}{k_str}: {val_str}")

		if level > 0:
			lines.append(f"{indent_str}}}")
			return "\n".join(lines)
		else:
			return "\n".join(lines) # Root level doesn't need wrapping brackets usually, but BlueMap accepts them.

	elif isinstance(obj, list):
		# Check if list contains simple dicts (like points) that should be one-liners
		is_simple_points = len(obj) > 0 and isinstance(obj[0], dict) and "x" in obj[0]

		if is_simple_points:
			lines = ["["]
			for item in obj:
				# Manually format points to keep them concise: { x: 1, y: 64, z: -23 }
				props = [f"{k}: {v}" for k, v in item.items()]
				lines.append(f"{next_indent}{{ {', '.join(props)} }}")
			lines.append(f"{indent_str}]")
			return "\n".join(lines)
		else:
			# Standard list
			return json.dumps(obj) # Fallback to JSON list for simple primitives

	elif isinstance(obj, str):
		return f'"{escape_hocon_string(obj)}"'
	elif isinstance(obj, bool):
		return str(obj).lower()
	else:
		return str(obj)

def load_json(uri):
	parsed = urlparse(uri)

	# Remote fetch for http/https
	if parsed.scheme in {"http", "https"}:
		try:
			with urlopen(uri, timeout=30) as resp:
				data = resp.read().decode("utf-8")
				return json.loads(data)
		except Exception as exc:
			print(f"⚠️ Failed to download {uri}: {exc}")
			return []

	# Local file fallback
	if not os.path.exists(uri):
		print(f"⚠️ {uri} not found.")
		return []
	with open(uri, 'r', encoding='utf-8') as f:
		return json.load(f)

def parse_args():
	parser = argparse.ArgumentParser(description="Generate BlueMap markers from JSON sources.")
	parser.add_argument(
		"-o",
		"--output",
		default=DEFAULT_OUTPUT_FILE,
		help="Output HOCON file path (default: config/maps/overworld_markers.conf)",
	)
	parser.add_argument(
		"--station-uri",
		default=DEFAULT_STATION_URI,
		help="Path or URI to station JSON (default: station.json)",
	)
	parser.add_argument(
		"--line-uri",
		default=DEFAULT_LINE_URI,
		help="Path or URI to line JSON (default: line.json)",
	)
	parser.add_argument(
		"--river-uri",
		default=DEFAULT_RIVER_URI,
		help="Path or URI to river JSON (default: river.json)",
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

	# Output
	hocon_content = to_hocon({"marker-sets": marker_sets})

	os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
	with open(output_file, 'w', encoding='utf-8') as f:
		f.write("# BlueMap Marker Config\n")
		f.write(hocon_content)

	print(f"✅ Generated {output_file} in BlueMap format.")

if __name__ == "__main__":
	args = parse_args()
	main(
		output_file=args.output,
		station_uri=args.station_uri,
		line_uri=args.line_uri,
		river_uri=args.river_uri,
	)
