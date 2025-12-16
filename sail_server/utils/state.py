# -*- coding: utf-8 -*-
# @file state.py
# @brief The State Bit
# @author sailing-innocent
# @date 2025-01-30
# @version 1.0
# ---------------------------------


class StateBits:
    __bits = bytearray(4)  # int -> 4 bytes
    __attrib_map = {}

    def __init__(self, state: int):
        self.set_state(state)

    def set_state(self, state: int):
        self.__bits = bytearray(state.to_bytes(4, byteorder="little"))

    def set_attrib_map(self, attrib_map: dict):
        self.__attrib_map = attrib_map

    # 32 bit bool array
    def __getitem__(self, index: int):
        if index < 0 or index >= 32:
            raise IndexError("StateBits only support 0-31")
        return (self.__bits[index // 8] >> (index % 8)) & 1

    def __setitem__(self, index: int, value: int):
        if index < 0 or index >= 32:
            raise IndexError("StateBits only support 0-31")
        if (value > 1) or (value < 0):
            raise ValueError("StateBits only support 0 or 1")
        if value:
            self.__bits[index // 8] |= 1 << (index % 8)
        else:
            self.__bits[index // 8] &= ~(1 << (index % 8))

    def set_attrib(self, attrib: str):
        if attrib not in self.__attrib_map:
            raise ValueError("Attribute not found")
        self[self.__attrib_map[attrib]] = 1

    def unset_attrib(self, attrib: str):
        if attrib not in self.__attrib_map:
            raise ValueError("Attribute not found")
        self[self.__attrib_map[attrib]] = 0

    def is_attrib(self, attrib: str):
        if attrib not in self.__attrib_map:
            raise ValueError("Attribute not found")
        return self[self.__attrib_map[attrib]]

    @property
    def value(self):
        return int.from_bytes(self.__bits, byteorder="little")

    def __repr__(self):
        return f"StateBits({self.value})"

    def __str__(self):
        return bin(self.value)[2:].zfill(32)

    # operator |=, &=, ^=, ~
    def __ior__(self, other):
        self.set_state(self.value | other.value)
        return self

    def __iand__(self, other):
        self.set_state(self.value & other.value)
        return self

    def __ixor__(self, other):
        self.set_state(self.value ^ other.value)
        return self

    def __invert__(self):
        self.set_state(~self.value)
        return self

    # operator ==
    def __eq__(self, other):
        return self.value == other.value
