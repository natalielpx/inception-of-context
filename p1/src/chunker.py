import hashlib
import tree_sitter_cpp as tscpp
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
	
	NON_CODE = {".ini", ".yml", ".yaml", ".md", ".txt"}

	QUERY_SOURCE = """
	(function_definition) @function
	(class_specifier) @class
	(struct_specifier) @struct
	(preproc_include) @include
	"""

	def __init__(self):
		self.language = Language(tscpp.language())
		self.parser = Parser(self.language)
		self.query = Query(self.language, self.QUERY_SOURCE)

	def fromFile(self, path: str, text: str) -> Chunk:
		return Chunk(path, "non-code", text, 1)

	def fromNode(self, filepath: str, kind: str, node) -> Chunk:
		text = node.text.decode("utf-8", errors="replace")
		start_line = node.start_point.row + 1
		return Chunk(filepath, kind, text, start_line)

	def chunk(self, filepath: str) -> list[Chunk]:

		path = Path(filepath)

		if path.suffix in self.NON_CODE:
			return [self.fromFile(filepath, path.read_text())]

		tree = self.parser.parse(path.read_bytes())
		captures = QueryCursor(self.query).captures(tree.root_node)
		captured = {n.id for nodes in captures.values() for n in nodes}

		chunks = []

		for kind, nodes in captures.items():
			for node in nodes:
				chunks.append(self.fromNode(filepath, kind, node))

		for child in (c for c in tree.root_node.children if c.id not in captured):
			chunks.append(self.fromNode(filepath, "other", child))

		return chunks