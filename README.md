# vnovel_generation

Builds upon Xiaoyu Han's project to automate the generation of visual novels about research ethics.

## Usage

TODO

## Config

The questions should be in the `questions.yaml`. Its syntax should be:

```yaml
situations:
  - question: "The 1st question that should be asked in the visual novel"
    answers:
      - "Answer 0"
      - "Answer 1"
      # ...
      - "Answer n"
    correct_answer: 0 # The index of the correct answer, starting with 0.
  # ...
  - question: "The n-th question that should be asked in the visual novel"
    answers:
      - "Answer 0"
      - "Answer 1"
      # ...
      - "Answer n"
    correct_answer: 0
```

See the actual `questions.yaml` file for an example.