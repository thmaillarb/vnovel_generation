#!/usr/bin/env python3
import yaml
from ollama import Client


class Situation:
    """
    Used to represent a question and its answers, generally obtained from the YAML file.
    """

    def __init__(self, question: str, correct_answer_index: int, answers: tuple):
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
    with open("questions.yaml", "r") as file:
        questions_yaml = yaml.safe_load(file)

    situations = list()
    for situation in questions_yaml['situations']:
        question = situation["question"]
        answers = tuple(situation["answers"])
        correct_answer = situation["correct_answer"]
        obj = Situation(question, correct_answer, answers)
        situations.append(obj)

    ollama_client = Client(host="http://localhost:11434", timeout=20 * 60)  # 20 minutes of timeout

    # TODO Improvement (?), use .format if it doesn't recreate the whole string every time
    for situation in situations:
        prompt = f"Create a story based on this question: {situation.question}. The possible answers are:\n"
        for i in range(len(situation.answers)):
            prompt += f"{i}. {situation.answers[i]}\n"

        prompt += f"The correct answer is {situation.correct_answer} and is the only one to lead to a good ending. " \
                  f"The other answers are wrong answers and must always lead to a bad ending, with severe " \
                  f"consequences for all the characters involved. Write the story with an introduction, leading to " \
                  f"the choice to make. You have to write the different endings each option lead to. Do not reword " \
                  f"the choices. The story must be written in a first person point of view. The format should be this " \
                  f"(replace each part of the format by the corresponding element:\n" \
                  "Introduction\n" \
                  "========================\n"

        for i in range(len(situation.answers)):
            prompt += f"Answer {i}: {situation.answers[i]}\n" \
                      f"Ending with answer {i}\n" \
                      "-----------------------"

        response = ollama_client.chat(
            model="gemma2:9b",
            messages=[
                {
                    'role': 'user',
                    'content': prompt
                }
            ]
        )


