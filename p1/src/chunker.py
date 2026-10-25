import hashlib
import pprint
import tree_sitter_cpp as tscpp
import tree_sitter_yaml as tsyml
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from tree_sitter import Language, Parser, Query, QueryCursor


@dataclass
class Chunk:

	path: str
	kind: str
	text: str
	start_line: int
	end_line: int = field(init=False)
	hash_value: str = field(init=False)
	chunk_id: str = field(init=False)
	point_id: str = field(init=False)

	def __post_init__(self):
		self.end_line = self.start_line + max(len(self.text.splitlines()), 1) - 1
		self.hash_value = hashlib.sha256(self.text.encode()).hexdigest()
		self.chunk_id = f"{self.path}:{self.start_line}-{self.end_line}"
		self.point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, self.chunk_id))


class Chunker:
	
	YML_CODE = {".yml", ".yaml"}
	CPP_CODE = {".cpp", ".hpp", ".h", ".cc", ".tpp", ".inl", ".tpp", ".ipp"}
	TYPES = frozenset({
		"function_definition",
		"class_specifier",
		"struct_specifier",
		"enum_specifier",
		"namespace_definition",
		"template_declaration",
		"declaration"
	})
	OTHER = -1

	def __init__(self):
		self.parser_yml = Parser(Language(tsyml.language()))
		self.parser_cpp = Parser(Language(tscpp.language()))

	def from_file(self, filepath: str, text: str) -> Chunk:
		return Chunk(filepath, "non-code", text, 1)

	def from_node(self, filepath: str, node) -> Chunk:
		kind = "error" if node.has_error else "config"
		text = node.text.decode("utf-8", errors="replace")
		start_line = node.start_point.row + 1
		return Chunk(filepath, kind, text, start_line)

	def chunk_yml(self, filepath, data):

		# Parse file into nodes
		root = self.parser_yml.parse(data).root_node
		if root.is_error:
			return [self.from_file(filepath, data.decode("utf-8", errors="replace"))]
		
		# Collect meaningful nodes
		nodes = []
		for d in (c for c in root.children if c.type == "document"):
			for b in (c for c in d.children if c.type == "block_node"):
				for m in (c for c in b.children if c.type == "block_mapping"):
					nodes.extend(c for c in m.children if c.type == "block_mapping_pair" or c.is_error)
		if not nodes:
			return [self.from_file(filepath, data.decode("utf-8", errors="replace"))]
		
		# Join comments/other into neighbouring nodes
		chunks = []
		cuts = [0] + [node.start_byte for node in nodes[1:]] + [len(data)]
		for node, start, end in zip(nodes, cuts, cuts[1:]):
			chunks.append(self.from_node(filepath, node))
		return chunks

	def chunk_cpp(self, filepath, data):

		# Parse data into nodes
		text = data.decode("utf-8", errors="replace")
		lines = text.splitlines()
		root = self.parser_cpp.parse(data).root_node
		# Unwrap include guard (needed for .h .hpp files); keep comments in nodes
		top = [n for n in root.named_children if n.type != "comment"]
		nodes = root.named_children
		if len(top) == 1 and top[0].type == "preproc_ifdef":
			nodes = top[0].named_children

		owner = [None] * len(lines)
		comment_rows = set()

		for i, n in enumerate(nodes):
			start = n.start_point[0]
			# ensure nodes do not include trailing empty new line
			end = n.end_point[0] - 1 if n.end_point[1] == 0 else n.end_point[0]
			end = min(end, len(lines) - 1)
			if n.type == "comment":
				comment_rows.update(range(start, end + 1))
			elif n.type in self.TYPES:
				for row in range(start, end + 1):
					owner[row] = i

		# Nothing recognised: whole file as one chunk
		if all(o is None for o in owner):
			return [self.from_file(filepath, text)]

		# Bottom-up: decide what happens to every line without a node
		for row in range(len(lines) - 1, -1, -1):
			if owner[row] is not None:
				continue
			if not lines[row].strip():
				continue
			# comment directly above a node joins that node;
			# stacked comment lines chain upward because we go bottom-up
			if row in comment_rows and row + 1 < len(lines):
				below = owner[row + 1]
				if below is not None and below != self.OTHER:
					owner[row] = below
					continue
			# everything else: includes, macros, guard lines, trailing comments
			owner[row] = self.OTHER

		# Group consecutive lines of same owner into chunks
		chunks = []
		start = 0
		for row in range(1, len(lines) + 1):
			if row < len(lines) and owner[row] == owner[start]:
				continue
			current = owner[start]
			if current is not None:
				kind = "other" if current == self.OTHER else nodes[current].type
				chunk = Chunk(filepath, kind, "\n".join(lines[start:row]), start + 1)
				chunks.append(chunk)
			start = row
		return chunks


	def chunk(self, filepath: str) -> list[Chunk]:
		path = Path(filepath)
		try:
			data = path.read_bytes()
		except OSError as e:
			raise OSError(f"[chunk] cannot read {filepath}: {e}")
		if path.suffix in self.YML_CODE:
			return self.chunk_yml(filepath, data)
		if path.suffix in self.CPP_CODE:
			return self.chunk_cpp(filepath, data)
		return [self.from_file(filepath, data.decode("utf-8", errors="replace"))]
