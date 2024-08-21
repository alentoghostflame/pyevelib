from __future__ import annotations

from contextlib import contextmanager
from logging import getLogger
from pathlib import Path
from typing import BinaryIO, NamedTuple


logger = getLogger(__name__)


__all__ = ("load",)


class NestedData(NamedTuple):
    indent: int
    """Amount of indentation compared to the previous level"""
    data: dict | list


class NestedString(NestedData):
    indent: int
    """Amount of indentation compared to the previous level"""
    data: str


class YamlWorkaroundLoad:
    file: BinaryIO
    data_layers: list[NestedData]

    def on_line(self, raw_data: bytes, decoded_data: str):
        if decoded_data.strip() == "":
            # Empty whitespace, ignore it.
            return
        elif decoded_data.strip().startswith("#"):
            # Commented out, ignore it.
            return

        # logger.debug('Processing line "%s"', decoded_data.rstrip("\n"))

        current_indent_level = get_list_indent(decoded_data) or get_indent_level(decoded_data)

        # logger.debug(
        #     "Data layer sum indent %s vs current line indent %s.",
        #     self.sum_layer_indent,
        #     current_indent_level,
        # )

        while current_indent_level < (temp := self.sum_layer_indent):
            popped_layer = self.pop_data_layer()
            # logger.debug(
            #     "Current indent %s vs top layer indent %s, popped a layer to reduce by %s.",
            #     current_indent_level,
            #     temp,
            #     popped_layer.indent,
            # )

        if current_indent_level > temp:
            logger.warning(
                "Current indent %s is greater than top layer indent %s, something may not be right.",
                current_indent_level,
                temp,
            )
            raise ValueError("weh")

        if not self.handle_list(decoded_data, current_indent_level) and not self.handle_dict(
            decoded_data, current_indent_level
        ):
            raise ValueError(f'Cannot handle line "{decoded_data}".')

    def handle_list(self, decoded_data: str, current_indent_level: int) -> bool:
        if strip_indent(decoded_data).startswith("- "):
            # logger.debug("List data detected.")
            # logger.debug(f'Decoded data: "%s", given current indent: "%s"', decoded_data.rstrip("\n"), current_indent_level)


            if isinstance(self.top_layer.data, dict) and current_indent_level > get_indent_level(decoded_data):
                # logger.debug("Detected list entry right after dict, popping data layer.")
                self.pop_data_layer()

            if not isinstance(self.top_layer.data, list):
                raise ValueError(f"Expected list layer, got {type(self.top_layer.data)}")

            if get_dict_value(decoded_data):
                # logger.debug("Detected dict in list data, creating dict layer and handling it.")
                new_dict = {}
                dict_indent = get_stripped_list_indent(decoded_data) - current_indent_level
                # logger.error("%s %s %s", dict_indent, get_stripped_list_indent(decoded_data), current_indent_level)
                self.top_layer.data.append(new_dict)
                self.add_data_layer(dict_indent, new_dict)
                self.handle_dict(decoded_data, current_indent_level + dict_indent)
            else:
                val = handle_value(strip_list_indent(decoded_data))
                # TODO: Handle block strings.
                self.top_layer.data.append(val)

            return True
        else:
            return False

    def handle_dict(self, decoded_data: str, current_indent_level: int) -> bool:
        if dict_data := get_dict_value(decoded_data):
            # logger.debug("Dict data detected.")
            if not isinstance(self.top_layer.data, dict):
                raise ValueError(f"Expected dict layer, got {type(self.top_layer.data)}")

            if dict_data[1] == {}:
                # raise NotImplementedError("Future dict not supported yet.")
                # logger.debug("Future nesting detected.")
                with self.read_future_line() as (future_full_raw_data, future_raw_data, future_decoded_data):
                    future_indent_level = get_list_indent(future_decoded_data) or get_indent_level(
                        future_decoded_data
                    )
                    if future_indent_level < current_indent_level:
                        raise ValueError(
                            f"Future indent level {future_indent_level} is less than current indent level "
                            f"{current_indent_level}? {dict_data}"
                        )

                    if strip_indent(future_decoded_data).startswith("- "):
                        # logger.debug("Future list detected, creating list layer.")
                        new_list = []
                        list_indent = get_list_indent(future_decoded_data) - current_indent_level
                        self.top_layer.data[dict_data[0]] = new_list
                        self.add_data_layer(list_indent, new_list)
                    else:
                        # logger.debug("Future dict detected, creating dict layer.")
                        new_dict = {}
                        dict_indent = future_indent_level - current_indent_level
                        self.top_layer.data[dict_data[0]] = new_dict
                        self.add_data_layer(dict_indent, new_dict)

            else:
                if isinstance(dict_data[1], str):
                    self.top_layer.data[dict_data[0]] = self.get_text_block(
                        dict_data[1], current_indent_level
                    )
                else:
                    self.top_layer.data[dict_data[0]] = dict_data[1]

            return True
        else:
            return False

    @property
    def sum_layer_indent(self) -> int:
        return sum([nest.indent for nest in self.data_layers])

    @property
    def top_layer(self) -> NestedData:
        return self.data_layers[-1]

    def add_data_layer(self, indent: int, pointer: list | dict):
        self.data_layers.append(NestedData(indent, pointer))

    def pop_data_layer(self) -> NestedData:
        return self.data_layers.pop()

    @contextmanager
    def read_future_line(self):
        full_data = b""
        try:
            while (line_data := self.file.readline()).strip() == b"" or line_data.startswith(b"#"):
                # To skip all blank and commented lines.
                # logger.debug("Skipped future blank line.")
                full_data += line_data

            full_data += line_data
            # logger.debug("Yielding future of %s", full_data)
            yield full_data, line_data, line_data.decode()

        finally:
            # logger.debug("Rewinding to present.")
            self.file.seek(-len(full_data), 1)

    def get_text_block(self, starting_string: str, current_indent: int) -> str:
        ret = starting_string

        stop_string: str | None = None
        # TODO: Re-add handling quotations and ignoring symbols.
        if starting_string[0] in ('"', "'"):
            stop_string = starting_string[0]
            # logger.debug("Stop string (%s) detected.", stop_string)
            index = find_stop_string(starting_string[1:], stop_string)
            if index is None:
                pass  # The stop string isn't in this, pass to the next lines.
            elif index != len(starting_string) - 2:
                raise ValueError(
                    f'Found characters outside of starting_string stop_string: "{starting_string}", index {index}'
                )
            else:
                # Found the stop string, we are done.
                return starting_string.strip(stop_string)

        while (raw_data := self.file.readline()) != b"":
            decoded_data = raw_data.decode()
            if decoded_data.strip() == "":
                # Empty whitespace, add a new line.
                ret += "\n"
                continue

            if stop_string is None:
                if get_indent_level(decoded_data) <= current_indent:
                    # logger.debug("Indent level decrease below current indent, reversing read and leaving.")
                    self.file.seek(-len(raw_data), 1)
                    break
            else:
                if (index := find_stop_string(decoded_data, stop_string)) is None:
                    pass  # The stop string isn't in this line, pass to the next one.
                elif index != len(decoded_data.rstrip()) - 1:
                    raise ValueError(
                        f'Found characters outside of decoded_data stop_string: "{decoded_data.rstrip()}"'
                    )
                else:
                    # Found the stop string, we are done.
                    ret += " " + decoded_data.strip().rstrip(stop_string)
                    return ret

            ret += " " + decoded_data.strip()

        return ret.strip()

    @classmethod
    def load(cls, file_path: str) -> dict | list:
        loader = cls()
        line_count = 0  # TODO: Remove.
        logger.debug('Loading file at "%s" using pyyaml workaround.', file_path)
        with open(file_path, "rb") as file:
            loader.file = file
            with loader.read_future_line() as (future_full_data, future_raw_data, future_decoded_data):
                if future_decoded_data.strip().startswith("- "):
                    # logger.debug("Starting with a list.")
                    ret = []
                    loader.data_layers = [NestedData(2, ret)]
                else:
                    # logger.debug("Starting with a dict.")
                    ret = {}
                    loader.data_layers = [NestedData(0, ret)]

            while (raw_data := file.readline()) != b"":
                line_count += 1
                decoded_data = raw_data.decode()
                try:
                    loader.on_line(raw_data, decoded_data)
                except Exception as e:
                    logger.critical("Error occurred on line %s, '%s'", line_count, decoded_data)
                    raise e

            logger.debug("EOF reached, returning.")

            # return ret
            return loader.data_layers[0].data


def load(file_path: str | Path) -> dict | list:
    return YamlWorkaroundLoad.load(str(file_path))


def find_stop_string(given_text: str, stop_string: str) -> int | None:
    # The replacement is because \" and "" do not count.
    # Replacing them with a dummy character prevents splitting on them.
    split_text = (
        given_text.replace(f"\\{stop_string}", "~~")
        .replace(stop_string + stop_string, "~~")
        .split(stop_string)
    )
    # if given_text.startswith(stop_string):
    #     return 0
    if len(split_text) == 1:
        return None
    ret_index = 0
    for index, segment in enumerate(split_text):
        ret_index += len(segment)
        return ret_index
    return None


def get_dict_value(given_line: str) -> tuple[int | str, int | str | dict] | None:
    # TODO: List support?
    given_line = strip_indent(given_line).strip()
    for index, char in enumerate(given_line):
        if char == ":":
            if len(given_line) == index + 1:
                return handle_value(strip_list_indent(given_line[:index])), {}
            elif given_line[index + 1] == " ":
                return handle_value(strip_list_indent(given_line[:index])), handle_value(
                    given_line[index + 1 :]
                )

    return None


def handle_value(given: str) -> str | int | float | bool | list:
    given = given.strip()
    if (temp := given.replace(".", "")).isnumeric():
        if temp != given:
            return float(given)
        else:
            return int(given)
    # if given.isdecimal():
    #     return int(given)
    # elif given.isnumeric():
    #     return float(given)
    elif given in ("true",):
        return True
    elif given in ("false",):
        return False
    elif given.startswith("[") and given.endswith("]"):
        split_given = given[1:-1].split(",")
        if len(split_given) > 1:
            ret = []
            for val in split_given:
                ret.append(handle_value(val))

            return ret

        else:
            return []

    else:
        return given


def get_indent_level(line: str) -> int:
    return len(line) - len(strip_indent(line))


def strip_indent(line: str) -> str:
    return line.lstrip(" ")


def get_list_indent(line: str) -> int | None:
    if strip_indent(line).startswith("- "):
        return len(line.split("- ")[0]) + 2

    return None


def get_stripped_list_indent(line: str) -> int:
    return len(line) - len(strip_list_indent(line))


def strip_list_indent(line: str) -> str:
    return line.lstrip("- ")
