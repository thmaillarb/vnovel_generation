#!/usr/bin/env python3
import traceback
from time import time
import yaml
from ollama import Client
import re
import sys
import zipfile
import os
import torch
from diffusers import StableDiffusion3Pipeline

def no_blank_line(text):
    lines = text.split("\n")
    non_empty_lines = [line for line in lines if line.strip() != ""]
    ret = "\n".join(non_empty_lines)
    return "\n".join(non_empty_lines)


def talk(line, characters_lowercase):
    dialogue = line.partition(":")
    talker = dialogue[0].strip()
    if talker.lower() in characters_lowercase:
        talker_index = characters_lowercase.index(talker.lower())
        spoken_line = bytes(dialogue[2], 'utf-8').decode("utf-8", 'ignore')
        spoken_line = spoken_line.replace("\"", "\\\"")
        return f'    c{talker_index} "{spoken_line}"\n'
    elif talker.lower() in ["me", "you"]:
        spoken_line = bytes(dialogue[2], 'utf-8').decode("utf-8", 'ignore')
        spoken_line = spoken_line.replace("\"", "\\\"")
        return f'    me "{spoken_line}"\n'
    else:
        spoken_line = bytes(dialogue[0], 'utf-8').decode("utf-8", 'ignore')
        spoken_line = spoken_line.replace("\"", "\\\"")
        return f'    "{spoken_line}"\n'

class Dialogue:
    def __init__(self, line, speaker = None):
        self._speaker = speaker
        self._line = line.replace("\"", "\\\"")

    @property
    def line(self):
        return self._line

    @property
    def speaker(self):
        return self._speaker

    def renpy_line(self, characters):
        if self._speaker:
            c_index = characters.index(self._speaker)
            return f'c{c_index} "{self._line}"'
        else:
            return f'"{self._line}"'

    def __str__(self):
        return self._line

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
        self._characters = set()

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
        """:obj:`list` of :obj:`Dialogue` he generated introduction for this Situation. Should be assigned by parse()."""
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
        story = "\n".join([str(x) for x in self.introduction + [self.correct_answer] + self.good_ending])
        return story

    @property
    def characters(self):
        return self._characters

    def parse(self, story):
        """Parses the story generated by AI.

        :param story: the generated story.
        :type story: str
        """
        story_per_line = story.split("\n")
        dialogues_dict = dict()  # Dictionary line => dialogue
        i = story_per_line.index("| Speaker | Dialogue |") + 2  # skipping header of table and "|---|---|" line
        while True:
            if i == len(story_per_line) or not story_per_line[i].strip():
                break
            line = story_per_line[i][2:-2].split("|")
            speaker = line[0].strip()
            dialogue = line[1].strip()

            #escaped_dialogue = re.escape(dialogue)
            #words = escaped_dialogue.split(" ")
            words = dialogue.split()

            # pattern = r'\b.*?\b'.join(words)
            pattern = r""
            for word in words[:-1]:
                pattern += re.escape(word)
                pattern += r'.*?'
            pattern += words[-1]

            dialogues_dict[pattern] = speaker
            i += 1

        # introduction
        i = story_per_line.index("## Introduction") + 2
        self._introduction = list()
        while True:
            if story_per_line[i].startswith("##") or story_per_line[i+1].startswith("## "):
                break

            if not story_per_line[i].strip():
                i += 1
                continue

            for pattern, speaker in dialogues_dict.items():
                added = False
                self._characters.add(speaker)
                if re.search(pattern, story_per_line[i], re.DOTALL):
                    dialogue_line = Dialogue(story_per_line[i], speaker)
                    self._introduction.append(dialogue_line)
                    added = True
                    break

            if added:
                dialogues_dict.pop(pattern)
            else:
                dialogue_line = Dialogue(story_per_line[i])
                self._introduction.append(dialogue_line)

            i += 1

        # endings
        self._endings = list()
        for i in range(len(self._answers)):
            j = story_per_line.index(f"## Ending with answer {i}") + 2
            ending = list()
            while True:
                if story_per_line[j].startswith("## ") or story_per_line[j+1].startswith("## "):
                    break
                if story_per_line[j] == "":
                    j += 1
                    continue

                for pattern, speaker in dialogues_dict.items():
                    added = False
                    self._characters.add(speaker)
                    if re.search(pattern, story_per_line[j], re.DOTALL):
                        dialogue_line = Dialogue(story_per_line[j], speaker)
                        ending.append(dialogue_line)
                        added = True
                        break

                if added:
                    dialogues_dict.pop(pattern)
                else:
                    dialogue_line = Dialogue(story_per_line[j])
                    ending.append(dialogue_line)

                j += 1
            self._endings.append(ending)

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
    background_prompts = list()

    # Generating a story for each situation
    # TODO Improvement (?), use .format if it doesn't recreate the whole string every time
    while True:
        try:
            for situation in situations:
                print(f"# Situation {situations.index(situation)}")
                prompt = f"Create a story based on this question: {situation.question}. The possible answers are:\n"
                # List of possible answers. The number of answers is undefined, hence the for loop.
                for i in range(len(situation.answers)):
                    prompt += f"{i}. {situation.answers[i]}\n"

                prompt += f"The correct answer is {situation.correct_answer} and is the only one to lead to a good ending. " \
                          f"The other answers are wrong answers and must always lead to a bad ending, with severe " \
                          f"consequences for all the characters involved. Write the story with an introduction, leading to " \
                          f"the choice to make. You have to write all the different endings each option lead to. Do not reword " \
                          f"the choices. The good ending must be at least 3 paragraphs long. The story must be " \
                          f"written in a third person point of view. The story must be more dialogue than description " \
                          f"because it is a visual novel. For each line, one character can talk at most. The format " \
                          f"should be markdown. After finishing the story, " \
                          f"list all the dialogues with the speakers name, preferably in a table." \
                          f"The format of the story should be this " \
                          f"(replace each part of the format by the corresponding element):\n" \
                          "## Introduction\n"

                # Better results if we're explicitly asking for each answer

                for i in range(len(situation.answers)):
                    prompt += f"## Ending with answer {i}\n"
                prompt += "## Dialogues\n"
                # Gemma 2 gives better sounding stories in our opinion and has a more consistent format
                response = ollama_client.chat(
                    model="gemma2:9b",
                    messages=[
                        {
                            'role': 'system',
                            'content': "Paragraphs must be no longer than 40 words."
                        },
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
                situation.parse(response["message"]["content"])

                str_intro = "\n".join([str(x) for x in situation.introduction])

                prompt = f"Describe where this scene takes place. You must describe the " \
                         f"location of the scene with what the reader might imagine, in a neutral way. You must be " \
                         f"objective, not subjective. Don't write sentences, " \
                         f"only keywords. You are not allowed to write keywords that refer to people, humans, " \
                         f"or body:\n{str(str_intro)}"
                response = ollama_client.chat(
                    model="llama3:8b",
                    messages=[
                        {
                            "role": "system",
                            "content": "Respond with 70 words or less. You are not allowed to write keywords that "
                                       "refer to people, humans, or body. You must only write the keywords."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    options={
                        "top_p": 0.1,
                        "temperature": 0.1
                    }
                )
                print(response["message"]["content"])
                background_prompts.append(response["message"]["content"])



            # Generating transitions
            transitions = list()
            print("Generating transitions")
            for i in range(len(situations) - 1):
                str_intro = '\n'.join([str(x) for x in situations[i + 1].introduction])
                # Compiling the correct path of the 1st story.
                prompt = "Write a transition between these two texts. They are part of the same story. The narrator is the " \
                         "same person. Write only the transition of the story. The transition must feel natural. The first " \
                         "text describes events happening before those of the second text.\n" \
                         f"Here is the first text: '{situations[i].good_story}'\n\n" \
                         f"Here is the second text: '{str_intro}'"

                # Using llama3 because it's better at actually giving a chronological transition.
                response = ollama_client.chat(
                    model="llama3:8b",
                    messages=[
                        {
                            'role': 'system',
                            'content': 'Paragraphs must be no longer than 40 words.'
                        },
                        {
                            'role': 'user',
                            'content': prompt
                        }
                    ],
                    options={
                        'top_p': 0.8
                    }
                )

                transition = response["message"]["content"].encode("utf-8", "ignore").decode(
                    "utf-8").replace("\"", "\\\"")
                transitions.append(transition)
                pass
            break
        except Exception as e:
            print(traceback.print_exc(file=sys.stderr))
            print("Retrying...", file=sys.stderr)
            situations = list()
            transitions = list()
            background_prompts = list()

    print("Generating backgrounds")
    # initializing Stable Diffusion 3
    pipe = StableDiffusion3Pipeline.from_pretrained(
        "stabilityai/stable-diffusion-3-medium-diffusers",
        torch_dtype=torch.float16
    )
    pipe = pipe.to("cuda")
    for i in range(len(background_prompts)):
        image = pipe(
            prompt=f'anime background image of {background_prompts[i]}',
            negative_prompt="humans, bad anatomy, people, person, character, characters",
            num_inference_steps=50,
            height=576,
            width=1024,
            guidance_scale=7
        ).images[0]

        image.save(f"bg{i}.png")

    del pipe
    torch.cuda.empty_cache()

    print("Getting character list")

    all_characters = list()
    for situation in situations:
        for character in situation.characters:
            if character not in all_characters:
                all_characters.append(character)

    print("Extracting base game")

    t = int(time())
    game_name = f"vnai-{t}"
    with zipfile.ZipFile("base.zip", "r") as f:
        f.extractall(game_name)

    print("Configuring the game")
    with open(f"{game_name}/base/game/options.rpy", "a") as f:
        f.write(f'define config.save_directory = "{game_name}"')

    for i in range(len(situations)):
        os.rename(f"bg{i}.png", f"{game_name}/base/game/images/bg{i}.png")

    print("Generating the script")

    with open(f"{game_name}/base/game/script.rpy", "a", encoding="utf8") as f:
        # Registering characters
        for i in range(len(all_characters)):
            f.write(f'define c{i} = Character("{all_characters[i]}")\n')

        f.write("label start:\n")
        f.write("    jump story0\n")

        # Writing each situation
        for i in range(len(situations)):
            print(f"Writing situation {i}")
            f.write(f"label story{i}:\n")
            f.write(f"    scene bg{i} at image_upscale\n")
            f.write(f"    with dissolve\n")

            # Introduction
            for line in situations[i].introduction:
                f.write(f'    {line.renpy_line(all_characters)}\n')

            # Choice
            f.write("    menu:\n")
            for j in range(len(situations[i].answers)):
                answer = situations[i].answers[j]
                f.write(f'        "{answer}":\n')
                f.write(f'            jump s{i}a{j}\n')

            # Endings
            for j in range(len(situations[i].endings)):
                f.write(f"label s{i}a{j}:\n")
                for line in situations[i].endings[j]:
                    f.write(f'    {line.renpy_line(all_characters)}\n')

                if j == situations[i].correct_answer_index:
                    if i + 1 == len(situations):
                        f.write("    jump ending\n")
                    else:
                        for line in transitions[i].split('\n'):
                            f.write(f'    "{line}"\n')
                        f.write(f"    jump story{i+1}\n")
                else:
                    f.write(f"    jump story{i}\n")


        # final ending
        f.write(
            "label ending:\n"
            '    "Thanks for playing!"\n'
        )

        f.flush()
        os.fsync(f.fileno())

    os.system(f'powershell -command "Get-Content .\\{game_name}\\base\\game\\script.rpy | Set-Content -Encoding utf8 .\\{game_name}\\base\\game\\script-tmp.rpy"')
    os.remove(f"{game_name}/base/game/script.rpy")
    os.rename(f"{game_name}/base/game/script-tmp.rpy", f"{game_name}/base/game/script.rpy")
