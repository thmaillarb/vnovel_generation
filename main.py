#!/usr/bin/env python3

class Situation:
    """
    Used to represent a question and its answers, generally obtained from the YAML file.
    """
    def __int__(self, question: str, correct_answer_index: int, *answers: str):
        """
        Constructor of the Situation class.

        Args:
            question (str): The question of this situation. Corresponds to the question key in the YAML file.
            correct_answer_index (int): The index of the correct answer in the *answers tuple (starting with 0).
            *answers (str): The possible answers to this situation. There must be at least 2 answers.
        """
        if len(answers) <= 1:
            raise ValueError(f"There should be at least 2 possible answers ({len(answers)} provided)")
        if correct_answer_index < 0 or correct_answer_index >= len(answers):
            raise ValueError(f"correct_answer should be between 0 and {len(answers)}")
        self._question = question
        self._answers = answers
        self._correct_answer_index = correct_answer_index

    @property
    def question(self):
        """str: the question to be asked in this situation."""
        return self._question

    @property
    def answers(self):
        """:obj:`tuple` of :obj:`str`: the tuple of all possible answers."""
        return self._answers

    @property
    def correct_answer_index(self):
        """int: the index of the correct answer in the answers tuple."""
        return self._correct_answer_index

    @property
    def correct_answer(self):
        """str: the text of the correct answer"""
        return self._answers[self._correct_answer_index]

if __name__ == '__main__':
    # reading questions

    pass
