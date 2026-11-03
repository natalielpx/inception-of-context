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

	@staticmethod
	def rows(n, nlines):
		# ensure nodes do not include trailing empty new line
		start = n.start_point[0]
		end = n.end_point[0] - 1 if n.end_point[1] == 0 else n.end_point[0]
		return start, min(end, nlines - 1)

	def _select_yml(self, data, lines):

		root = self.parser_yml.parse(data).root_node
		nodes = []
		for d in (c for c in root.children if c.type == "document"):
			for b in (c for c in d.children if c.type == "block_node"):
				for m in (c for c in b.children if c.type == "block_mapping"):
					nodes.extend(c for c in m.children if c.type == "block_mapping_pair" or c.is_error)
		comments = {i for i, l in enumerate(lines) if l.lstrip().startswith("#")}
		return nodes, comments

	def _select_cpp(self, data, lines):

		root = self.parser_cpp.parse(data).root_node
		top = [n for n in root.named_children if n.type != "comment"]
		children = root.named_children
		# Unwrap include guard (needed for .h .hpp files)
		if len(top) == 1 and top[0].type == "preproc_ifdef":
			children = top[0].named_children
		comments = set()
		for n in children:
			if n.type == "comment":
				start, end = self.rows(n, len(lines))
				comments.update(range(start, end + 1))
		nodes = [n for n in children if n.type in self.TYPES]
		return nodes, comments

	def _from_file(self, filepath: str, text: str) -> Chunk:
		return Chunk(filepath, "non-code", text, 1)
	
	def _from_lines(self, filepath, lines, nodes, comments):

		owner = [None] * len(lines)
		for i, n in enumerate(nodes):
			start, end = self.rows(n, len(lines))
			for row in range(start, end + 1):
				owner[row] = i

		# Bottom-up: decide what happens to every line without a node
		for row in range(len(lines) - 1, -1, -1):
			if owner[row] is not None or not lines[row].strip():
				continue
			# comment directly above a node joins that node;
			# stacked comment lines chain upward
			if row in comments and row + 1 < len(lines):
				below = owner[row + 1]
				if below is not None and below != self.OTHER:
					owner[row] = below
					continue
			# includes, macros, guard lines, trailing comments
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
		if b"\0" in data or not data.strip():	# binary, or empty
			return []
		try:
			text = data.decode("utf-8")
		except UnicodeDecodeError:
			return []
		lines = text.split("\n")

		nodes = []
		if path.suffix in self.YML_CODE:
			nodes, comments = self._select_yml(data, lines)
		elif path.suffix in self.CPP_CODE:
			nodes, comments = self._select_cpp(data, lines)
		if not nodes:
			return [self._from_file(filepath, text)]

		return self._from_lines(filepath, lines, nodes, comments)
