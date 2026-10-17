#!/usr/bin/env python3
"""
Tests for message template expansion.

These build members in memory rather than reading the data directory, so they
run the same with or without real data.

Run with:
    ./venv/bin/python -m unittest discover tests -v
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models import Member  # noqa: E402
from utils.template_expander import SmartTemplateExpander  # noqa: E402


class FakeTemplates:
    pleasantries = {}


def member(member_id=1, first='David', last='Smith', gender='M', **kwargs):
    return Member(member_id=member_id, first_name=first, last_name=last,
                  gender=gender, phone='', birthday='',
                  recommend_expiration='', **kwargs)


def expand(text, who, **kwargs):
    return SmartTemplateExpander(FakeTemplates()).expand(text, who, **kwargs)


class TestPronouns(unittest.TestCase):

    def test_a_boy_is_he_him_his(self):
        self.assertEqual(expand('{he} {him} {his}', member(gender='M')),
                         'he him his')

    def test_a_girl_is_she_her_her(self):
        self.assertEqual(expand('{he} {him} {his}', member(gender='F')),
                         'she her her')

    def test_no_recorded_gender_names_both(self):
        self.assertEqual(expand('{he} {him} {his}', member(gender='')),
                         'he/she him/her his/her')

    def test_pronouns_mix_with_other_variables(self):
        text = expand('Hope {he} has a great day, {child_name}!',
                      member(first='Anna', gender='F'), child_name='Anna')
        self.assertEqual(text, 'Hope she has a great day, Anna!')


class TestNamingSeveralPeople(unittest.TestCase):

    def setUp(self):
        self.david = member(1, 'David', 'Smith', 'M')
        self.lisa = member(2, 'Lisa', 'Smith', 'F')
        self.jones = member(3, 'Lisa', 'Jones', 'F')

    def names(self, people, text='{name|blue?formal:casual}'):
        return expand(text, people[0], addressees=people)

    def test_one_person_reads_as_before(self):
        self.assertEqual(self.names([self.david], '{name|x?formal:casual}'), 'David')
        self.assertEqual(self.names([self.lisa], '{name|x?casual:formal}'), 'Sister Smith')
        self.assertEqual(self.names([self.david], '{name|x?full:full} {full_name}'),
                         'David Smith David Smith')

    def test_a_couple_casually(self):
        self.assertEqual(self.names([self.david, self.lisa]), 'David & Lisa')

    def test_a_couple_formally_when_either_has_the_flag(self):
        self.lisa.flag = 'blue'
        self.assertEqual(self.names([self.david, self.lisa]), 'Brother and Sister Smith')

    def test_a_couple_with_different_last_names_formally(self):
        self.jones.flag = 'blue'
        self.assertEqual(self.names([self.david, self.jones]),
                         'Brother Smith and Sister Jones')

    def test_full_names(self):
        self.assertEqual(self.names([self.david, self.lisa], '{full_name}'),
                         'David and Lisa Smith')
        self.assertEqual(self.names([self.david, self.jones], '{full_name}'),
                         'David Smith and Lisa Jones')

    def test_the_husband_is_named_first_whatever_order_they_come_in(self):
        self.assertEqual(self.names([self.lisa, self.david], '{full_name}'),
                         'David and Lisa Smith')

    def test_aka_is_used(self):
        self.david.aka = 'Dave'
        self.assertEqual(self.names([self.david, self.lisa], '{first_name}'), 'Dave & Lisa')

    def test_parent_greeting_names_parents_with_different_last_names(self):
        from utils.template_expander import greeting
        self.jones.flag = 'blue'
        self.assertEqual(greeting([self.david, self.jones]),
                         'Brother Smith and Sister Jones')
        self.assertEqual(greeting([self.jones]), 'Sister Jones')
        self.assertEqual(greeting([self.david]), 'David')


class TestShippedTemplates(unittest.TestCase):
    """The shipped templates should not talk about one child as 'they'."""

    def test_parent_templates_do_not_use_they_for_the_child(self):
        import re
        import yaml
        with open(ROOT / 'data' / 'message_templates.yaml', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        offenders = []
        for activity, entries in data.items():
            if not isinstance(entries, dict):
                continue
            for name, text in entries.items():
                if (name.endswith('_parent') and isinstance(text, str)
                        and re.search(r'\b(they|them|their)\b', text, re.I)):
                    offenders.append(f'{activity}.{name}')
        self.assertEqual(offenders, [])


if __name__ == '__main__':
    unittest.main()
