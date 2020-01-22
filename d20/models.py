import abc
import random

from . import errors

__all__ = (
    "Number", "Expression", "Literal", "UnOp", "BinOp", "Parenthetical", "Set", "Dice", "Die",
    "SetOperator", "SetSelector"
)


class Number(abc.ABC):  # num
    __slots__ = ("kept", "annotation")

    def __init__(self):
        self.kept = True
        self.annotation = None

    @property
    def number(self):
        """
        Returns the numerical value of this object.

        :rtype: int or float
        """
        return sum(n.number for n in self.keptset)

    @property
    def total(self):
        """
        Returns the numerical value of this object with respect to whether it's kept.
        Generally, this is preferred to use over ``number``, as this will return 0 if
        the number node was dropped.

        :rtype: int or float
        """
        return self.number if self.kept else 0

    @property
    def set(self):
        """
        Returns the set representation of this object.

        :rtype: list of Number
        """
        raise NotImplementedError

    @property
    def keptset(self):
        """
        Returns the set representation of this object, but only including children whose values
        were not dropped.

        :rtype: list of Number
        """
        return [n for n in self.set if n.kept]

    def drop(self):
        """
        Makes the value of this Number node not count towards a total.
        """
        self.kept = False

    @property
    def children(self):
        """Returns a list of Numbers that this Number is a parent of."""
        raise NotImplementedError

    def __int__(self):
        return int(self.total)

    def __float__(self):
        return float(self.total)


class Expression(Number):
    __slots__ = ("roll", "comment")

    def __init__(self, roll, comment):
        """
        :type roll: Number
        """
        super().__init__()
        self.roll = roll
        self.comment = comment

    @property
    def number(self):
        return self.roll.number

    @property
    def set(self):
        return self.roll.set

    @property
    def children(self):
        return [self.roll]


class Literal(Number):
    __slots__ = ("values", "exploded")

    def __init__(self, value):
        """
        :type value: int or float
        """
        super().__init__()
        self.values = [value]  # history is tracked to support mi/ma op
        self.exploded = False

    @property
    def number(self):
        return self.values[-1]

    @property
    def set(self):
        return [self]

    @property
    def children(self):
        return []

    def explode(self):
        self.exploded = True

    def update(self, value):
        """
        :type value: int or float
        """
        self.values.append(value)


class UnOp(Number):
    __slots__ = ("op", "value")

    UNARY_OPS = {
        "-": lambda v: -v,
        "+": lambda v: +v
    }

    def __init__(self, op, value):
        """
        :type op: str
        :type value: Number
        """
        super().__init__()
        self.op = op
        self.value = value

    @property
    def number(self):
        return self.UNARY_OPS[self.op](self.value.total)

    @property
    def set(self):
        return [self]

    @property
    def children(self):
        return [self.value]


class BinOp(Number):
    __slots__ = ("op", "left", "right")

    BINARY_OPS = {
        "+": lambda l, r: l + r,
        "-": lambda l, r: l - r,
        "*": lambda l, r: l * r,
        "/": lambda l, r: l / r,
        "//": lambda l, r: l // r,
        "%": lambda l, r: l % r,
        "<": lambda l, r: int(l < r),
        ">": lambda l, r: int(l > r),
        "==": lambda l, r: int(l == r),
        ">=": lambda l, r: int(l >= r),
        "<=": lambda l, r: int(l <= r),
        "!=": lambda l, r: int(l != r),
    }

    def __init__(self, left, op, right):
        """
        :type op: str
        :type left: Number
        :type right: Number
        """
        super().__init__()
        self.op = op
        self.left = left
        self.right = right

    @property
    def number(self):
        try:
            return self.BINARY_OPS[self.op](self.left.total, self.right.total)
        except ZeroDivisionError:
            raise errors.RollValueError("Cannot divide by zero.")

    @property
    def set(self):
        return [self]

    @property
    def children(self):
        return [self.left, self.right]


class Parenthetical(Number):
    __slots__ = ("value", "operations")

    def __init__(self, value, operations=None):
        """
        :type value: Number
        :type operations: list of SetOperator
        """
        super().__init__()
        if operations is None:
            operations = []
        self.value = value
        self.operations = operations

    @property
    def number(self):
        return self.value.number

    @property
    def total(self):
        return self.value.total if self.kept else 0

    @property
    def set(self):
        return self.value.set

    @property
    def children(self):
        return self.value.children


class Set(Number):
    __slots__ = ("values", "operations")

    def __init__(self, values, operations=None):
        """
        :type values: list of Number
        :type operations: list of SetOperator
        """
        super().__init__()
        if operations is None:
            operations = []
        self.values = values
        self.operations = operations

    @property
    def set(self):
        return self.values

    @property
    def children(self):
        return self.values


class Dice(Set):
    __slots__ = ("num", "size", "_context")

    def __init__(self, num, size, values, operations=None, context=None):
        """
        :type num: int
        :type size: int
        :type values: list of Die
        :type operations: list of SetOperator
        :type context: dice.RollContext
        """
        super().__init__(values, operations)
        self.num = num
        self.size = size
        self._context = context

    @classmethod
    def new(cls, num, size, context=None):
        return cls(num, size, [Die.new(size, context=context) for _ in range(num)], context=context)

    def roll_another(self):
        self.values.append(Die.new(self.size, context=self._context))

    @property
    def children(self):
        return []


class Die(Number):  # part of diceexpr
    __slots__ = ("size", "values", "_context")

    def __init__(self, size, values, context=None):
        """
        :type size: int
        :type values: list of Literal
        :type context: dice.RollContext
        """
        super().__init__()
        self.size = size
        self.values = values
        self._context = context

    @classmethod
    def new(cls, size, context=None):
        inst = cls(size, [], context=context)
        inst._add_roll()
        return inst

    @property
    def number(self):
        return self.values[-1].total

    @property
    def set(self):
        return [self.values[-1]]

    @property
    def children(self):
        return []

    def _add_roll(self):
        if self.size < 1:
            raise errors.RollValueError("Cannot roll a 0-sided die.")
        if self._context:
            self._context.count_roll()
        n = Literal(random.randrange(self.size) + 1)  # 200ns faster than randint(1, self._size)
        self.values.append(n)

    def reroll(self):
        if self.values:
            self.values[-1].drop()
        self._add_roll()

    def explode(self):
        if self.values:
            self.values[-1].explode()
        # another Die is added by the explode operator

    def force_value(self, new_value):
        if self.values:
            self.values[-1].update(new_value)


# noinspection PyUnresolvedReferences
# selecting on Dice will always return Die
class SetOperator:  # set_op, dice_op
    __slots__ = ("op", "sels")
    OPERATIONS = {"k", "p", "rr", "ro", "ra", "e", "mi", "ma"}

    def __init__(self, op, sels):
        """
        :type op: str
        :type sels: list of SetSelector
        """
        self.op = op
        self.sels = sels

    @classmethod
    def from_ast(cls, node):
        return cls(node.op, [SetSelector.from_ast(n) for n in node.sels])

    def select(self, target):
        """
        :type target: Number
        """
        out = set()
        for selector in self.sels:
            out.update(selector.select(target))
        return out

    def operate(self, target):
        """
        Operates in place on the values in a base set.

        :type target: Number
        """
        operations = {
            "k": self.keep,
            "p": self.drop,
            # dice only
            "rr": self.reroll,
            "ro": self.reroll_once,
            "ra": self.explode_once,
            "e": self.explode,
            "mi": self.minimum,
            "ma": self.maximum
        }

        operations[self.op](target)

    def keep(self, target):
        """
        :type target: Set
        """
        for value in target.keptset:
            if value not in self.select(target):
                value.drop()

    def drop(self, target):
        """
        :type target: Set
        """
        for value in self.select(target):
            value.drop()

    def reroll(self, target):
        """
        :type target: Dice
        """
        to_reroll = self.select(target)
        while to_reroll:
            for die in to_reroll:
                die.reroll()

            to_reroll = self.select(target)

    def reroll_once(self, target):
        """
        :type target: Dice
        """
        for die in self.select(target):
            die.reroll()

    def explode(self, target):
        """
        :type target: Dice
        """
        to_explode = self.select(target)
        already_exploded = set()

        while to_explode:
            for die in to_explode:
                die.explode()
                target.roll_another()

            already_exploded.update(to_explode)
            to_explode = self.select(target).difference(already_exploded)

    def explode_once(self, target):
        """
        :type target: Dice
        """
        for die in self.select(target):
            die.explode()
            target.roll_another()

    def minimum(self, target):  # immediate
        """
        :type target: Dice
        """
        selector = self.sels[-1]
        if selector.cat is not None:
            raise errors.RollValueError(f"{str(selector)} is not a valid selector for minimums.")
        the_min = selector.num
        for die in target.keptset:
            if die.number < the_min:
                die.force_value(the_min)

    def maximum(self, target):  # immediate
        """
        :type target: Dice
        """
        selector = self.sels[-1]
        if selector.cat is not None:
            raise errors.RollValueError(f"{str(selector)} is not a valid selector for maximums.")
        the_max = selector.num
        for die in target.keptset:
            if die.number > the_max:
                die.force_value(the_max)

    def __str__(self):
        return "".join([f"{self.op}{str(sel)}" for sel in self.sels])


class SetSelector:  # selector
    __slots__ = ("cat", "num")

    def __init__(self, cat, num):
        """
        :type cat: str or None
        :type num: int
        """
        self.cat = cat
        self.num = num

    @classmethod
    def from_ast(cls, node):
        return cls(node.cat, node.num)

    def select(self, target):
        """
        :type target: Number
        :return: The targets in the set.
        :rtype: set of Number
        """
        selectors = {
            "l": self.lowestn,
            "h": self.highestn,
            "<": self.lessthan,
            ">": self.morethan,
            None: self.literal
        }

        return set(selectors[self.cat](target))

    def lowestn(self, target):
        return sorted(target.keptset, key=lambda n: n.total)[:self.num]

    def highestn(self, target):
        return sorted(target.keptset, key=lambda n: n.total, reverse=True)[:self.num]

    def lessthan(self, target):
        return [n for n in target.keptset if n.total < self.num]

    def morethan(self, target):
        return [n for n in target.keptset if n.total > self.num]

    def literal(self, target):
        return [n for n in target.keptset if n.total == self.num]

    def __str__(self):
        if self.cat:
            return f"{self.cat}{self.num}"
        return str(self.num)