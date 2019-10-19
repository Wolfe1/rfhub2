from pathlib import Path
import re
from robot.errors import DataError
from robot.libdocpkg import LibraryDocumentation
import robot.libraries
from typing import Dict, List, Set, Tuple

from .api_client import Client


RESOURCE_PATTERNS = {".robot", ".txt", ".tsv", ".resource"}
ALL_PATTERNS = RESOURCE_PATTERNS | {".xml", ".py"}
EXCLUDED_LIBRARIES = {
    "remote.py",
    "reserved.py",
    "dialogs.py",
    "dialogs_jy.py",
    "dialogs_py.py",
    "dialogs_ipy.py",
    "setup.py",
}
INIT_FILES = {"__init__.txt", "__init__.robot", "__init__.html", "__init__.tsv"}
COLLECTION_KEYS = ("doc", "doc_format", "keywords", "name", "path", "scope", "type", "version")
KEYWORD_KEYS = ("name", "doc", "args")


class RfhubImporter(object):
    def __init__(
        self,
        client: Client,
        paths: Tuple[Path, ...],
        no_installed_keywords: bool,
        no_db_flush: bool,
    ) -> None:
        self.paths = paths
        self.no_installed_keywords = no_installed_keywords
        self.no_db_flush = no_db_flush
        self.client = client

    def delete_all_collections(self) -> Set[int]:
        """
        Deletes all existing collections.
        """
        collections_id = set()
        while len(self.client.get_collections()) > 0:
            collections_id.update(self._delete_collections())
        return collections_id

    def get_all_collections(self) -> List[Dict]:
        """Gets all collections from application"""
        collections = []
        for i in range(0, 999999, 100):
            collection_slice = self.client.get_collections(i, i+100)
            if len(collection_slice) == 0:
                break
            collections += collection_slice
        return collections

    def _delete_collections(self) -> Set[int]:
        """
        Helper method to delete all existing callections.
        """
        collections = self.client.get_collections()
        collections_id = {collection["id"] for collection in collections}
        for id in collections_id:
            self.client.delete_collection(id)
        return collections_id

    def import_libraries(self) -> Tuple[int, int]:
        """
        Import libraries to application from paths specified when invoking client.
        :return: Number of libraries loaded
        """
        libraries_paths = self.get_libraries_paths()
        collections = self.create_collections(libraries_paths)
        if not self.no_db_flush:
            loaded_collections = self.add_collections(collections)
        else:
            existing_collections = self.get_all_collections()
            collections_to_insert, collections_to_update = self.get_collections_for_update_and_insert(existing_collections, collections)
            collections_to_delete = self.get_obsolete_collections(existing_collections, collections)
            self.delete_outdated_collections(collections_to_delete)
            added_collections = self.add_collections(collections_to_insert)
            updated_collections = self.update_collections(collections_to_update)
            loaded_collections = added_collections + updated_collections
        return len(loaded_collections), sum(d["keywords"] for d in loaded_collections)

    def get_libraries_paths(self) -> Set[Path]:
        """
        Traverses all given paths and returns set with paths
        pointing to libraries to import to app.
        :return: Set of Paths object pointing to libraries to import
        """
        libraries_paths = set()
        for path in self.paths:
            libraries_paths.update(self._traverse_paths(Path(path)))
        if not self.no_installed_keywords:
            libdir = Path(robot.libraries.__file__).parent
            libraries_paths.update(self._traverse_paths(Path(libdir)))
        return libraries_paths

    def _traverse_paths(self, path: Path) -> Set[Path]:
        """
        Traverses through paths and adds libraries to rfhub.
        Helper function for get_library_paths.
        """
        valid_lib_paths = set()
        if self._is_library_with_init(path):
            valid_lib_paths.add(path)
        else:
            for item in path.iterdir():
                if item.is_dir():
                    if self._is_library_with_init(item):
                        valid_lib_paths.add(item)
                    else:
                        valid_lib_paths.update(self._traverse_paths(item))
                elif (
                    item.is_file()
                    and self._is_robot_keyword_file(item)
                    and not self._should_ignore(item)
                ):
                    valid_lib_paths.add(item)
        return valid_lib_paths

    def create_collections(self, paths: Set[Path]) -> List[Dict]:
        """
        Creates list of Collection objects from set of provided paths.
        :param paths: set of paths
        :return: list of Collection objects
        """
        collections = []
        for path in paths:
            try:
                collection = self.create_collection(path)
                collections.append(collection)
            except (DataError, SystemExit) as ex:
                print(
                    f"Failed to create collection from path {path}\n"
                    f"{type(ex).__name__}, {ex.args}"
                )
        return collections

    def create_collection(self, path: Path) -> Dict:
        """
        Creates Collection object from provided path.
        :param path: Path
        :return: Collection object
        """
        libdoc = LibraryDocumentation(str(path))
        serialised_keywords = self._serialise_keywords(libdoc)
        return self._serialise_libdoc(libdoc, str(path), serialised_keywords)

    def delete_outdated_collections(self, collections_ids: Set[int]) -> Set[int]:
        for collection_id in collections_ids:
            self.client.delete_collection(collection_id)
        return collections_ids

    def add_collections(self, collections: List[Dict]) -> List[Dict[str, int]]:
        """
        Adds collections and keywords from provided list to app.
        :param collections: List of collections object
        :return: list of dictionaries with collection name and number of keywords.
        """
        loaded_collections = []
        for collection in collections:
            coll_req = self.client.add_collection(collection)
            if coll_req[0] != 201:
                print(coll_req[1]["detail"])
                raise StopIteration
            collection_id = coll_req[1]["id"]
            for keyword in collection["keywords"]:
                keyword["collection_id"] = collection_id
                self.client.add_keyword(keyword)
            loaded_collections.append(
                {"name": collection["name"], "keywords": len(collection["keywords"])}
            )
            print(
                f'{collection["name"]} library with {len(collection["keywords"])} keywords loaded'
            )
        return loaded_collections

    def update_collections(self, collections: List[Dict]) -> List[Dict[str, int]]:
        """
        Updates collections and keywords from provided list to app.
        :param collections: List of collections object
        :return: list of dictionaries with collection name and number of keywords.
        """
        update_collections = []
        for collection in collections:
            coll_req = self.client.update_collection(collection, collection["id"])
            if coll_req[0] != 200:
                print(coll_req[1]["detail"])
                raise StopIteration
            for keyword in collection["keywords"]:
                if keyword["action"] == "delete":
                    self.client.delete_keyword(keyword["id"])
                elif keyword["action"] == "update":
                    self.client.update_keyword(keyword, keyword["id"])
                elif keyword["action"] == "insert":
                    self.client.add_keyword(keyword)
            update_collections.append(
                {"name": collection["name"], "keywords": len(collection["keywords"])}
            )
            print(
                f'{collection["name"]} library with {len([keyword for keyword in collection["keywords"] if keyword["action"] != "delete"])} keywords updated'
            )
        return update_collections

    def _serialise_libdoc(self, libdoc: Dict, path: str, keywords: Dict) -> Dict:
        """
        Serialises libdoc object to Collection object.
        :param libdoc: libdoc input object
        :param path: library path
        :return: Collection object
        """

        lib_dict = libdoc.__dict__
        lib_dict["doc_format"] = lib_dict.pop("_setter__doc_format")
        for key in ("_setter__keywords", "inits", "named_args"):
            lib_dict.pop(key)
        lib_dict["path"] = path
        lib_dict["keywords"] = keywords
        return lib_dict

    def _serialise_keywords(self, libdoc: Dict) -> Dict:
        """
        Serialises keywords to Keyword object.
        :param :libdoc input object
        :return: Keyword object
        """

        keywords = [keyword.__dict__ for keyword in libdoc.keywords]
        for keyword in keywords:
            keyword.pop("tags")
            if keyword["args"]:
                keyword["args"] = str(
                    [
                        str(item).replace("'", "").replace('"', "")
                        for item in keyword["args"]
                    ]
                ).replace("'", '"')
            else:
                keyword["args"] = ""
        return keywords

    @staticmethod
    def _is_library_with_init(path: Path) -> bool:
        return (path / "__init__.py").is_file() and len(
            LibraryDocumentation(str(path)).keywords
        ) > 0

    def _is_robot_keyword_file(self, file: Path) -> bool:
        return (
            self._is_library_file(file)
            or self._is_libdoc_file(file)
            or self._is_resource_file(file)
        )

    @staticmethod
    def _is_library_file(file: Path) -> bool:
        return file.suffix == ".py" and file.name != "__init__.py"

    @staticmethod
    def _is_libdoc_file(file: Path) -> bool:
        """Return true if an xml file looks like a libdoc file"""
        # inefficient since we end up reading the file twice,
        # but it's fast enough for our purposes, and prevents
        # us from doing a full parse of files that are obviously
        # not libdoc files
        if file.suffix == ".xml":
            with open(file, "r", encoding="utf-8", errors="ignore") as f:
                # read the first few lines; if we don't see
                # what looks like libdoc data, return false
                data = f.read(200)
                index = data.lower().find("<keywordspec ")
                return index > 0
        return False

    @staticmethod
    def _should_ignore(file: Path) -> bool:
        """Return True if a given library name should be ignored
        This is necessary because not all files we find in the library
        folder are libraries.
        """
        filename = file.name.lower()
        return (
            filename.startswith("deprecated")
            or filename.startswith("_")
            or filename in EXCLUDED_LIBRARIES
        )

    @staticmethod
    def _is_resource_file(file: Path) -> bool:
        """Returns true if the file has a keyword table but not a testcase table."""
        # inefficient since we end up reading the file twice,
        # but it's fast enough for our purposes, and prevents
        # us from doing a full parse of files that are obviously
        # not robot files

        if file.name not in INIT_FILES and file.suffix in RESOURCE_PATTERNS:
            with open(file, "r", encoding="utf-8", errors="ignore") as f:
                data = f.read()
                return not RfhubImporter._has_test_case_table(
                    data
                ) and RfhubImporter._has_keyword_table(data)
        return False

    @staticmethod
    def _has_keyword_table(data: str) -> bool:
        """Returns true if file has keyword or user keyword table"""
        return (
            re.search(
                r"^\*+\s*((?:User )?Keywords?)", data, re.MULTILINE | re.IGNORECASE
            )
            is not None
        )

    @staticmethod
    def _has_test_case_table(data: str) -> bool:
        """Returns true if file has keyword or user keyword table"""
        return (
            re.search(r"^\*+\s*(Test Cases?)", data, re.MULTILINE | re.IGNORECASE)
            is not None
        )

    def get_collections_for_update_and_insert(self, existing_collections: List[Dict], new_collections: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        collections_to_update = []
        collections_to_insert = []
        if len(existing_collections) >= 0:
            for new_collection in new_collections:
                for existing_collection in existing_collections:
                    reduced_collection = RfhubImporter._reduce_collection_items(existing_collection)
                    if RfhubImporter._collection_path_and_name_match(new_collection, reduced_collection):
                        if RfhubImporter._library_or_resource_changed(new_collection, reduced_collection):
                            new_collection["id"] = existing_collection["id"]
                            new_collection["keywords"] = RfhubImporter._get_keywords_actions(new_collection, existing_collection)
                            collections_to_update.append(new_collection)
            return collections_to_insert, collections_to_update
        return new_collections, collections_to_update

    @staticmethod
    def _get_collections_to_update(
        existing_collections: List[Dict], new_collections: List[Dict]
    ) -> List[Dict]:
        """Returns list of collections to update that were found in paths and application"""
        collections_to_update = []
        if len(existing_collections) >= 0:
            for new_collection in new_collections:
                for existing_collection in existing_collections:
                    reduced_collection = RfhubImporter._reduce_collection_items(
                        new_collection, existing_collection
                    )
                    if RfhubImporter._collection_path_and_name_match(
                        new_collection, reduced_collection
                    ):
                        if RfhubImporter._library_or_resource_changed(
                            new_collection, reduced_collection
                        ):
                            collections_to_update.append(new_collection)
        return collections_to_update

    def get_obsolete_collections(self,
        existing_collections: List[Dict], new_collections: List[Dict]
    ) -> Set[int]:
        """Returns set of collection ids that were found in application but not in paths"""
        return {
            existing_collection["id"]
            for existing_collection in existing_collections
            if all(
                existing_collection["path"] != new_collection["path"]
                for new_collection in new_collections
            )
        }

    @staticmethod
    def _get_outdated_collections(
        existing_collections: List[Dict], new_collections: List[Dict]
    ) -> Set[int]:
        """Returns set of collection ids that were found in application but are outdated"""
        outdated_collections = set()
        if len(existing_collections) > 0:
            outdated_collections = set()
            for new_collection in new_collections:
                for existing_collection in existing_collections:
                    reduced_collection = RfhubImporter._reduce_collection_items(
                        new_collection, existing_collection
                    )
                    if RfhubImporter._collection_path_and_name_match(
                        new_collection, reduced_collection
                    ) and RfhubImporter._library_or_resource_changed(
                        new_collection, reduced_collection
                    ):
                        outdated_collections.add(existing_collection["id"])
        return outdated_collections

    @staticmethod
    def _get_new_collections(
        existing_collections: List[Dict], new_collections: List[Dict]
    ) -> List[Dict]:
        """Returns list of collections to insert that were found in paths but not in application"""
        return [
            new_collection
            for new_collection in new_collections
            if all(
                new_collection["path"] != existing_collection["path"]
                for existing_collection in existing_collections
            )
        ]

    @staticmethod
    def _reduce_collection_items(existing_collection: Dict) -> Dict:
        reduced_collection = RfhubImporter._reduce_collection(existing_collection)
        reduced_collection["keywords"] = RfhubImporter._reduce_keywords(reduced_collection["keywords"])
        return reduced_collection

    @staticmethod
    def _reduce_collection(existing_collection: Dict) -> Dict:
        """Returns existing_collection dictionary with key/value pairs reduced to the ones from new_collection"""
        return {k: existing_collection[k] for k in COLLECTION_KEYS}

    @staticmethod
    def _reduce_keywords(existing_collection_keywords: List[Dict]) -> List[Dict]:
        """Returns existing_collection keys list of dictionaries
        with key/value pairs reduced to the ones from new_collection"""
        return [{k: v for k, v in keyword.items() if k in KEYWORD_KEYS} for keyword in existing_collection_keywords]

    @staticmethod
    def _collection_path_and_name_match(
        new_collection: Dict, existing_collection: Dict
    ) -> bool:
        return (
            new_collection["name"] == existing_collection["name"]
            and new_collection["path"] == existing_collection["path"]
        )

    @staticmethod
    def _library_or_resource_changed(
        new_collection: Dict, existing_collection: Dict
    ) -> bool:
        if new_collection["type"] == "library":
            return new_collection["version"] != existing_collection["version"]
        else:
            return new_collection != existing_collection

    @staticmethod
    def _get_keywords_actions(new_collection: List[Dict], existing_collection: List[Dict]) -> List[Dict]:
        """return list of dictionaries extended with one of actions: "update, insert, delete or skip` and keywords id"""
        keywords_with_actions = []
        reduced_keywords = RfhubImporter._reduce_keywords(existing_collection["keywords"])
        for new_keyword in new_collection["keywords"]:
            for reduced_keyword, existing_keyword in zip(reduced_keywords, existing_collection["keywords"]):
                if new_keyword == reduced_keyword:
                    new_keyword["action"] = "skip"
                elif new_keyword["name"] == reduced_keyword["name"]:
                    new_keyword["action"] = "update"
                    new_keyword["id"] = existing_keyword["id"]
                elif new_keyword not in reduced_keywords:
                    new_keyword["action"] = "insert"
                keywords_with_actions.append(new_keyword)

        for existing_keyword in existing_collection["keywords"]:
            if existing_keyword["name"] not in (new_keyword["name"] for new_keyword in new_collection["keywords"]):
                existing_keyword["action"] = "delete"
                keywords_with_actions.append(existing_keyword)
        return keywords_with_actions
