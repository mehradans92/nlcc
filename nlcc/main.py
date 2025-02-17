from .eval import eval_single, obj2html
from nlcc.openai import code_engine, nlp_engine
import os
from rich.markdown import Markdown
import pyperclip
from rich.syntax import Syntax
from rich.console import Console
from rich import pretty
from rich import inspect
from .nlp import Context, Prompt, guess_context, code_completion
from . import nlp
import click
from importlib_metadata import metadata
from .prompt import text_iter, Modes, PromptManager

pretty.install()


def process_n_response(query, console):
    try:
        new_n_responses = int(query)
    except ValueError as e:
        console.print(
            "\tFailed at setting n_responses with value:", query)
        return None
    if 1 > new_n_responses:
        console.print(
            "\tFailed at setting n_responses to value:", new_n_responses)
        console.print("\tn_responses must be an integer >= 1")
        return None
    return new_n_responses


def process_temperature(query, code_temp, nlp_temp, console):
    try:
        new_nlp_temp, new_code_temp = [float(s) for s in query.split(',')]
    except (ValueError, IndexError) as e:
        console.print(
            "\tFailed at setting temperature with command:", query)
        return
    if 0 > new_code_temp or new_code_temp > 1:
        console.print(
            "\tFailed at setting code temperature with command:", query)
        console.print("\tTemperature out of range [0,1]")
        return
    else:
        code_temp = new_code_temp
        console.print("\tSetting code🧊 query temperature to", code_temp)

    if 0 > new_code_temp or new_code_temp > 1:
        console.print(
            "\tFailed at setting GPT3 temperature with command:", query)
        console.print("\tTemperature out of range [0,1]")
        return
    else:
        nlp_temp = new_nlp_temp
        console.print("\tSetting GPT3🔥 query temperature to", nlp_temp)
    return code_temp, nlp_temp


def get_engine(engine, console=None):
    if engine == 'openai':
        if console:
            console.print('Using OpenAI Engine💰💰💰')
        from .openai import nlp_engine, code_engine
    elif engine == 'huggingface':
        if console:
            console.print('Using Huggingface Engine🤗🤗🤗')
        from .huggingface import nlp_engine
    else:
        if console:
            console.print('Unkown engine', engine)
        exit(1)
    return nlp_engine, code_engine


_DEFAULT_NLP_T = 0.3
_DEFAULT_CODE_T = 0.0


@click.command()
@click.argument('input_file', default=None, required=False)
@click.option('--n_responses', default=1)
@click.option('--engine', default='openai')
@click.option('--help', is_flag=True)
def main(input_file, engine, help, n_responses):
    console = Console()
    context = Context("", Prompt())
    pm = PromptManager()
    code_temp, nlp_temp = _DEFAULT_CODE_T, _DEFAULT_NLP_T

    nlp_engine, code_engine = get_engine(engine, console)

    def query_file_text(input_file, context):
        if not os.path.exists(input_file):
            console.print(f"Input file not found: {input_file}")
            return None
        query = open(input_file, 'r').read()
        context = code_completion(
            query, context, code_engine, T=code_temp, n=n_responses)
        response_text = context.responses
        for idx, response in enumerate(response_text):
            if len(response_text) > 1:
                console.print(f"## Option {idx+1}")
            console.print(Syntax(query, context.prompt.language,
                                 theme='monokai', line_numbers=True))
            console.print(Syntax(response, context.prompt.language,
                                 theme='monokai', line_numbers=True))
        return context

    if input_file is not None:
        context = Context("", Prompt())
        query_file_text(input_file, context)
        exit()

    # welcome message
    readme = metadata('nlcc')['Description']
    kb_info = readme.split('## key bindings')[-1]
    help_message = '# 🧠 nlcc 🧠 \n' + '## Info on keybinds\n' + kb_info

    console.print(Markdown(help_message))
    if(help):
        exit()

    def help(e):
        console.print()
        console.print(Markdown(help_message))

    # make it here to have access to context
    def make_copy(e):
        if context is not None:
            pyperclip.copy(context.text)
            console.print('\n✨copied✨')
        else:
            console.print('\n🤔 nothing to copy')

    def status(e):
        console.print()
        console.print(Markdown(
            f'# 🧠 nlcc Status 🧠\n - nlp🔥: `T = {nlp_temp}` \n- code🧊: `T = {code_temp}` \n- n_responses🤏: `N = {n_responses}` '))
        inspect(context, title='Context',  docs=False)
        if len(pm) > 1:
            inspect(pm, title='Input Mode', docs=False)

    def reset_context(e):
        nonlocal context
        context = Context("", Prompt())
        pm.pop()
        pm.push('👋', Modes.SELECT_CONTEXT)

    def responses(e):
        pm.push('num_responses🥳', Modes.SELECT_NRESPONSE)

    def temperature(e):
        pm.push('🔥🧊', Modes.TEMPERATURE)
        console.print(
            f'\nEnter as 0.7,0.2. Currently nlp🔥:{nlp_temp} code🧊: {code_temp}', end='')

    def execute(e):
        g = {}
        console.print()
        exec(context.text, g)

    def write(e):
        pm.push('filename✍️📝', Modes.WRITE_FILE)

    def read(e):
        pm.push('filename👀📝', Modes.READ_FILE)

    kbs = {'c-w': make_copy, 'c-o': reset_context, 'c-z': execute, 'c-n': responses,
           'c-q': help, 'c-u': status, 'c-t': temperature, 'c-x': write, 'c-l': read}
    for i, query in enumerate(text_iter(pm, kbs)):

        if query.lower() == 'exit' or query.lower() == 'q' or query.lower() == 'quit':
            break
        elif pm.peek_mode() == Modes.SELECT_NRESPONSE:
            new_n = process_n_response(query, console)
            if new_n is not None:
                n_responses = new_n
        elif pm.peek_mode() == Modes.TEMPERATURE:
            new_t = process_temperature(
                query, code_temp, nlp_temp, console)
            if new_t is not None:
                code_temp, nlp_temp = new_t
        elif pm.peek_mode() == Modes.SELECT_CONTEXT:
            context = guess_context(query, nlp_engine, nlp_temp)
        elif pm.peek_mode() == Modes.READ_FILE:
            context_returned = query_file_text(query, context)
            if type(context_returned) == type(context):
                context = context_returned
        elif pm.peek_mode() == Modes.WRITE_FILE:
            if context:
                if query and os.path.normpath('(path-to-wiki)/foo/bar.txt').startswith('(path-to-wiki)'):
                    with open(query, 'w') as f:
                        f.write(context.text + '\n')
                        console.print(
                            f'✨wrote to {query}✨')
                else:
                    console.print(f'🤔 Not sure about this filepath: {query}')
            else:
                console.print('🤔 nothing to write')
        elif pm.peek_mode() == Modes.SELECT_RESPONSE:
            try:
                i = int(query) - 1
                context.text = context.responses[i]
                console.print(Syntax(context.text, context.prompt.language,
                                     theme='monokai', line_numbers=True))
                context.responses = None
            except Exception as e:
                console.print(e)
                console.print('🤮 what was that? Please pick response')
                continue
        else:
            context = code_completion(
                query, context, code_engine, T=code_temp, n=n_responses)
            if len(context.responses) == 1:
                context.text = context.responses[0]
                console.print(Syntax(context.text, context.prompt.language,
                                     theme='monokai', line_numbers=True))
                context.responses = None
            else:
                for ridx, r in enumerate(context.responses):
                    console.print(f"## Option {ridx+1}")
                    console.print(Syntax(r, context.prompt.language,
                                         theme='monokai', line_numbers=True))
                pm.push('🤔which response', Modes.SELECT_RESPONSE)
                # do not want pop
                continue

        # reset mode
        pm.pop()
        if len(pm) == 0:
            pm.push(context.name if len(context.name) >
                    1 else 'context-free', Modes.QUERY)


@click.command()
@click.argument('yaml-files', type=click.Path(exists=True), nargs=-1)
@click.option('--n', default=1, help='number of respones')
@click.option('--engine', default='openai')
@click.option('--terminal',default=False,is_flag=True)
@click.option('--temperature', default=0.2)
def eval(yaml_files, n, engine, temperature, terminal):
    if terminal is True:
        console = Console()
    from tabulate import tabulate
    nlp_engine, code_engine = get_engine(engine)
    table = []
    collapsables = []
    for y in yaml_files:
        report, info = eval_single(y, engine=code_engine, n=n, T=temperature)
        if terminal is True:
            context = report["context"] 
            console.print(Syntax(info, context.prompt.language,
                        theme='monokai', line_numbers=False))
            for ridx, r in enumerate(context.responses):
                console.print(f"## Option {ridx+1}")
                console.print(Syntax(r, context.prompt.language,
                        theme='monokai', line_numbers=True))
            console.print(report['name'])
            console.print(report['result'])
            continue
        if report is None:
            exit(1)
        collapsables.append(f'''
<details>
    <summary>{report['name']}</summary>
    {info}
</details>
        ''')
        table.append([report['name']] +
                     ['Pass' if r else 'Fail' for r in report['result']])
    if terminal is True:
        return
    print('## Test Report')
    print('### Global Parameters')
    print('* Engine = ', engine)
    print('* n = ', n)
    print('## Results')
    print(tabulate(table, ['Test'] +
                   [f'Run {i}' for i in range(n)], tablefmt="github"))
    print('## Test Details')
    print('\n'.join(collapsables))


@click.command()
def prompts():
    collapsables = []
    for n, p in nlp.prompts.items():
        collapsables.append(f'''
<details>
    <summary>{n}</summary>
    {obj2html(p)}
</details>
        ''')
    pyperclip.copy('\n'.join(collapsables))
    print('I put them on your clipboard. Hopefully you wanted that!!')
