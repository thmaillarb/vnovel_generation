#!/usr/bin/env python3
import ntpath
import sys
import traceback

import yaml
from ollama import Client
import re
import zipfile
from time import time
import os


def no_blank_line(text):
    lines = text.split("\n")
    non_empty_lines = [line for line in lines if line.strip() != ""]
    ret = "\n".join(non_empty_lines)
    return "\n".join(non_empty_lines)


def talk(line, characters_lowercase):
    line = line.replace("\"", "\\\"")
    return f'    "{line}"\n'


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
        self._introduction = None
        self._endings = None

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

    @property
    def introduction(self):
        """str: he generated introduction for this Situation. Should be assigned by parse()."""
        return self._introduction

    @property
    def endings(self):
        """:obj:`list` of :obj:`str`: the tuple storing all endings of this Situation. Should be assigned by parse().

        The indexes of this tuple match the indexes of the correct_answer tuple.
        """
        return self._endings

    @property
    def good_ending(self):
        """str: returns the good ending of this Situation."""
        return self._endings[self._correct_answer_index]

    @property
    def good_story(self):
        if self._introduction is None or self._endings is None:
            raise AttributeError("Introduction and/or endings undefined - have you run parse()?")
        return "\n".join((
            self.introduction,
            self.correct_answer,
            self.good_ending
        ))

    def parse(self, story):
        """Parses the story generated by AI.

        :param story: the generated story.
        :type story: str
        """
        story = re.sub(r"(\*\*|##)", "", story)
        self._introduction = re.search(r"=*(.+?)\n+?(--+|==+|Answer [0-9]+)", story, flags=re.DOTALL).group(1)
        self._introduction = self._introduction.replace(".",".\n")
        self._introduction = no_blank_line(self._introduction)

        if self._introduction is None:
            raise Exception("Couldn't generate/parse the introduction.")

        self._endings = list()
        for match in re.finditer(r"(Ending with answer [0-9]+:?\n)?--+\n(.+?)(--+|pini|Answer [0-9])", story,
                                 flags=re.DOTALL):
            ending = match.group(2)
            ending = ending.replace(".",".\n")
            ending = no_blank_line(ending)
            if ending is None:
                self._introduction = None
                self._endings = None
                raise Exception("An ending couldn't be generated or parsed.")
            self._endings.append(ending)
        if len(self._endings) != len(self._answers):
            self._introduction = None
            self._endings = None
            raise Exception("Couldn't generate/parse properly: there isn't the same amount of endings and of answers")


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

    transitions = list()

    # Generating a story for each situation
    # TODO Improvement (?), use .format if it doesn't recreate the whole string every time
    while True:
        try:
            for situation in situations:
                print(f"Situation {situations.index(situation)}")
                prompt = f"Create a story based on this question: {situation.question}. The possible answers are:\n"
                # List of possible answers. The number of answers is undefined, hence the for loop.
                for i in range(len(situation.answers)):
                    prompt += f"{i}. {situation.answers[i]}\n"

                prompt += f"The correct answer is {situation.correct_answer} and is the only one to lead to a good ending. " \
                          f"The other answers are wrong answers and must always lead to a bad ending, with severe " \
                          f"consequences for all the characters involved. Write the story with an introduction, leading to " \
                          f"the choice to make. You have to write all the different endings each option lead to. Do not reword " \
                          f"the choices. The good ending must be at least 3 paragraphs long. The story must be " \
                          f"written in a first person point of view. The format of the story should be this " \
                          f"(replace each part of the format by the corresponding element):\n" \
                          "Introduction\n" \
                          "========================\n"

                # Better results if we're explicitly asking for each answer
                for i in range(len(situation.answers)):
                    prompt += f"Answer {i}: {situation.answers[i]}\n" \
                              f"Ending with answer {i}\n" \
                              f"-----------------------\n"
                # Gemma 2 gives better sounding stories in our opinion and has a more consistent format
                response = ollama_client.chat(
                    model="gemma2:9b",
                    messages=[
                        {
                            'role': 'user',
                            'content': prompt
                        }
                    ],
                    options={
                        'top_p': 0.75
                    }
                )
                print(response["message"]["content"])
                situation.parse(
                    response["message"]["content"] + "\npini")  # Quick and dirty bugfix to recognise the last answer

            # Generating transitions
            transitions = list()
            for i in range(len(situations) - 1):
                # Compiling the correct path of the 1st story.
                prompt = "Write a transition between these two texts. They are part of the same story. The narrator is the " \
                         "same person. Write only the transition of the story. The transition must feel natural. The first " \
                         "text describes events happening before those of the second text.\n" \
                         "The format should be:\n" \
                         "Here is the transition" \
                         "======================" \
                         "(the actual transition)\n" \
                         f"Here is the first text: '{situations[i].good_story}'\n\n" \
                         f"Here is the second text: '{situations[i + 1].introduction}'"

                # Using llama3 because it's better at actually giving a chronological transition.
                response = ollama_client.chat(
                    model="llama3:8b",
                    messages=[
                        {
                            'role': 'user',
                            'content': prompt
                        }
                    ],
                    options={
                        'top_p': 0.8
                    }
                )

                # llama3 writes a sentence like "Sure, here's an example of transition" before giving the actual transition,
                # so we make sure to only get the transition (which always took one line when we tested it)
                response["message"]["content"] = response["message"]["content"].encode("utf-8", "ignore").decode(
                    "utf-8")
                transition = response["message"]["content"].splitlines()[-1]
                transition = transition.replace(".", ".\n")
                transition = no_blank_line(transition)
                transitions.append(transition)
            break
        except Exception as e:
            print(traceback.print_exc(file=sys.stderr))
            print("Retrying...", file=sys.stderr)

    print("Extracting base game")

    t = int(time())
    game_name = f"vnai-{t}"
    with zipfile.ZipFile("base.zip", "r") as f:
        f.extractall(game_name)

    print("Configuring the game")
    with open(f"{game_name}/base/game/options.rpy", "a") as f:
        f.write(f'define config.save_directory = "{game_name}"')

    print("Generating the script")

    with open(f"{game_name}/base/game/script-tmp.rpy", "w", encoding="utf8") as f:

        f.write("label start:\n")
        f.write("    jump story0\n")
        for i in range(len(situations)):
            print(f"Writing situation {i}")
            f.write(f"label story{i}:\n")
            for line in situations[i].introduction.split("\n"):
                f.write(talk(line, None))

            f.write("    menu:\n")
            for j in range(len(situations[i].answers)):
                answer = situations[i].answers[j]
                f.write(f'        "{answer}":\n')
                f.write(f'            jump s{i}a{j}\n')

            for j in range(len(situations[i].endings)):
                f.write(f"label s{i}a{j}:\n")
                for line in situations[i].endings[j].split("\n"):
                    f.write(talk(line, None))

                if j == situations[i].correct_answer_index:
                    if i + 1 == len(situations):
                        f.write("    jump ending\n")
                    else:
                        for line in transitions[i].split("\n"):
                            f.write(talk(line, None))
                        f.write(f"    jump story{i+1}\n")
                else:
                    f.write("    jump main_menu\n")

        f.write(
            "label ending:\n"
            '    "Thanks for playing!"\n'
        )
        f.write(
            "label main_menu:\n"
            "    return\n"
        )
        f.flush()
        os.fsync(f.fileno())

    os.system(f'powershell -command "Get-Content .\\{game_name}\\base\\game\\script-tmp.rpy | Set-Content -Encoding utf8 .\\{game_name}\\base\\game\\script.rpy"')
    os.remove(f"{game_name}/base/game/script-tmp.rpy")