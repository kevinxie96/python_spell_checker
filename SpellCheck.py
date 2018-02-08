import urllib.request
import sys
import string
import re

SET_OF_PUNC = set(".,!?;:")

# CONSTANTS
ORIGINAL_WORD_MULT = 80
STEP_SIZE = 2   # 1 or 2
C = 4000   # Association multiplier
MAX_EDIT_D = 2   # maximum edit distance
DATA_CUTOFF = 400000   # will find replacement even if it exists in either dictionary
MIN_ASSOCIATION_CONST = 1764374.424   # average of word count frequencies

# for small strings only
IMPLEMENT_SMALL_TEXT = False

class StringCorrection:
    def __init__(self,word_count_url,two_word_bigram_url):
        '''
        gets data on initialization
        word_count_url: string
            word count data
        two_word_bigram_url: string
            bigram count data
        '''
        # word count
        self.dic_words = {}
        for line in urllib.request.urlopen(word_count_url):
            word_count_pair = line.decode('UTF-8').rstrip().split("\t")
            self.dic_words[word_count_pair[0]] = int(word_count_pair[1])

        # bigram count
        self.dic_bigrams = {}
        for line in urllib.request.urlopen(two_word_bigram_url):
            words_count_pair = line.decode('UTF-8').rstrip().split("\t")
            self.dic_bigrams[words_count_pair[0]] = int(words_count_pair[1])

    def fix_errors(self,error_string):
        '''
        Main function which returns string with correct errors
        error_string: string
            string to analyze for errors
        '''
        error_list = re.findall(r"[\w']+|[.,!?:;]", error_string)

        # handle edge case of one string
        if len(error_list) == 1:
            return self.get_best_choice(error_list[0])

        i = 1
        while i < len(error_list):
            term_one, term_two = error_list[i-1], error_list[i]
            # when something like "?!" appears, skip forward 2 elements
            if term_one in SET_OF_PUNC and term_two in SET_OF_PUNC:
                i += 2

            # when something like "?!I" appears, skip forward an element
            elif term_one in SET_OF_PUNC:
                i += 1

            # when something like "Additionally," appears get best replacement for one word
            elif term_two in SET_OF_PUNC:
                if STEP_SIZE == 1:
                    if (i==1 or error_list[i-2] in SET_OF_PUNC):
                        error_list[i - 1] = self.handle_capitalization(term_one,self.get_best_choice(term_one.lower()))
                else:
                    error_list[i - 1] = self.handle_capitalization(term_one, self.get_best_choice(term_one.lower()))
                i += 2

            # when two words appear consecutively like "the fachs", get best replacement for both words
            else:
                error_list[i - 1],error_list[i] = self.handle_capitalization(
                    (term_one,term_two),
                    self.get_best_choice(term_one.lower(),term_two.lower())
                )
                i += STEP_SIZE

        # handle edge case of when last element is not punctuation i.e. it will skip last word without this
        if i == len(error_list) and error_list[-1] is not SET_OF_PUNC:
            error_list[-1] = self.get_best_choice(error_list[-1])
        return self.error_list_to_proper_str(error_list)

    def error_list_to_proper_str(self, error_list):
        return_string = ""
        for idx,val in enumerate(error_list):
            return_string = return_string + ("" if idx == 0 or val in SET_OF_PUNC else " ") + val
        return return_string

    def handle_capitalization(self,old_words,new_words):
        '''
        Returns replacements with proper capitalization
        old_words: string or list
            words to be replaced to check for capital
        new_words: string or list
            replacements to add capital
        '''
        old = old_words
        new = new_words
        if type(old) is tuple or type(old) is list:
            word_list = []
            for i in range(len(old)):
                if old[i][0].isupper():
                    word_list.append(new[i][0].upper() + new[i][1:])
                else:
                    word_list.append(new[i])
            return word_list
        else:
            if old[0].isupper():
                return new[0].upper() + new[1:]
            else:
                return new

    def get_best_choice(self,*arg):
        '''
        Returns the best replacement out of all the replacements. Could return tuple or string depending on *arg.
        *arg: string or tuple
            term(s) to find replacements for
        '''
        # One Word Case
        if len(arg) == 1:
            default = arg[0]
            one_srch_down = default in self.dic_words and self.dic_words[default] < DATA_CUTOFF
            replacements = self.find_options(default) if default not in self.dic_words or one_srch_down else [default]

            max_score = 0
            final_word = default
            for one in replacements:
                exists_in_either = one in self.dic_words or one in self.dic_bigrams
                score = self.dic_words.get(one) or self.dic_bigrams.get(one) if exists_in_either else 0
                if score > max_score:
                    max_score = score
                    final_word = one
            return final_word
        # Two Word Case
        elif len(arg) == 2:
            term_one = arg[0]
            term_two = arg[1]
            bigram = term_one + " " + term_two

            # booleans
            one_srch_down = term_one in self.dic_words and self.dic_words[term_one] < DATA_CUTOFF
            one_srch_up = term_one in self.dic_words and self.dic_words[term_one] > DATA_CUTOFF
            two_srch_down = term_two in self.dic_words and self.dic_words[term_two] < DATA_CUTOFF
            two_srch_up = term_two in self.dic_words and self.dic_words[term_two] > DATA_CUTOFF
            bi_srch_down = bigram in self.dic_bigrams and self.dic_bigrams[bigram] < DATA_CUTOFF
            one_neither = term_one not in self.dic_words and term_one not in self.dic_bigrams

            two_neither = term_two not in self.dic_words and term_two not in self.dic_bigrams
            if one_srch_up and two_srch_up and bigram not in self.dic_bigrams or bi_srch_down:
                replace_ones = self.find_options(term_one)
                replace_twos = self.find_options(term_two)
            else:
                replace_ones = self.find_options(term_one) if one_neither or (one_srch_down) else [term_one]
                replace_twos = self.find_options(term_two) if two_neither or (two_srch_down) else [term_two]

            if not replace_ones:
                replace_ones = [term_one]
            if not replace_twos:
                replace_ones = [term_two]
            max_score = 0
            final_bigram = (term_one,term_two)  # default value
            for replace_one in replace_ones:
                for replace_two in replace_twos:
                    # if term_one or term_two exists in word count, add a bonus to the score
                    C1 = 1 if replace_one != term_one else ORIGINAL_WORD_MULT
                    C2 = 1 if replace_two != term_two else ORIGINAL_WORD_MULT
                    bigram = replace_one + " " + replace_two
                    a_term_in_bigram = replace_one in self.dic_bigrams or replace_two in self.dic_bigrams

                    if replace_one in self.dic_words or replace_one in self.dic_bigrams:
                        word_one_score = self.dic_words.get(replace_one) or self.dic_bigrams.get(replace_one)
                    else:
                        word_one_score = 0

                    if replace_two in self.dic_words or replace_two in self.dic_bigrams:
                        word_two_score = self.dic_words.get(replace_two) or self.dic_bigrams.get(replace_two)
                    else:
                        word_two_score = 0

                    # reward association
                    if bigram in self.dic_bigrams:
                        association_score = C*self.dic_bigrams[bigram]
                    # If a term split happened, there are no longer two elements.
                    elif a_term_in_bigram:
                        association_score = self.dic_bigrams.get(replace_one) or self.dic_bigrams.get(replace_two)
                    # the wordset does not make sense, decrease the score
                    else:

                        association_score = -max(
                            word_one_score/(1 if len(replace_one) == 1 else len(replace_one)-1),
                            word_two_score/(1 if len(replace_one) == 1 else len(replace_one)-1),
                            MIN_ASSOCIATION_CONST
                        )
                    score = C1*word_one_score + C2*word_two_score + association_score
                    if score > max_score:
                        max_score = score
                        final_bigram = (replace_one,replace_two)
            return final_bigram
        else:
            raise ValueError("Program does not support n-grams n=3 and higher.")
        return

    def find_options(self, word):
        '''
        Returns a list of replacements which exist in word count or bigram count. Recurse until we get words of edit
        distance N, with N being the set of natural numbers
        word: string
            word to find replacements for
        '''
        def find(woi):
            add_options = ' ' + string.ascii_lowercase
            word_options = set([woi])
            for i in range(len(woi) + 1):
                if i < len(woi):
                    # delete
                    word_options.add(woi[:i] + woi[i + 1:])
                    # neighbor_swaps
                    if i > 0:
                        word_options.add(woi[:i - 1] + woi[i] + woi[i - 1] + woi[i + 1:])
                for option in add_options:
                    # add
                    word_options.add(woi[:i] + option + woi[i:])
                    # replace
                    if i < len(woi):
                        word_options.add(woi[:i] + option + woi[i + 1:])

            # words which exist in word count,list of words that are within the edit distance
            return [opt for opt in word_options if opt in self.dic_words or opt in self.dic_bigrams], word_options


        # hit the function once to see if word_to_return is populated
        words_to_return, word_options = find(word)

        # loop until word_to_return is populated, not surpassing MAX_EDIT_D edit distances, option for small texts to
        # find all replacements edit distance 2.
        count = 1
        if IMPLEMENT_SMALL_TEXT:
            while count < MAX_EDIT_D:
                temp_word_options = set()
                for option in word_options:
                    word_list = find(option)
                    words_to_return.extend(word_list[0])
                    temp_word_options.update(word_list[1])
                word_options = temp_word_options
                count += 1
            return words_to_return
        else:
            while not words_to_return and count < MAX_EDIT_D:
                temp_word_options = set()
                temp_words_to_return = set()
                for option in word_options:
                    word_list = find(option)
                    temp_words_to_return.update(word_list[0])
                    temp_word_options.update(word_list[1])
                word_options = temp_word_options
                words_to_return = temp_words_to_return
                count += 1
            return words_to_return
TEST_STRING = 'Among he many challenhes of writimgnis dealung with rules ofcorrect usage: whethwr to worry about split infinitives, fused articples, snd he meanings of words shch as "fortuyous", "decokate" anf "compruse".'
TEST_STRING2 = 'Supposedmy a riter has to choose beween tqo radically diffefentapproacjz to thede rules. Prescropgivists rescribe how language oufhr to beused. Tjey uphold srandards or excellence and a respect for the best of our civilisation, and are a bulwatk against relativism, vulgar populism and the dumbinfdown of literatr culture. Descriptovists descibe howlanguage actually isused. They bekuevethat thr rules of correct usqge arenpthing more than the secret handshake pf the rulijg clqds, designed to ker themasses untheir place.Language is an organicptoduct of human creativity, say the fescriptkvists, a d people ahould be allowed to write however theh please.'
TEST_STRING3 = 'Among he many challenhes of writimgnis dealung with rules ofcorrect usage: whethwr to worry about split infinitives, fused articples, snd he meanings of words shch as "fortuyous", "decokate" anf "compruse". Supposedmy a riter has to choose beween tqo radically diffefentapproacjz to thede rules. Prescropgivists rescribe how language oufhr to beused. Tjey uphold srandards or excellence and a respect for the best of our civilisation, and are a bulwatk against relativism, vulgar populism and the dumbinfdown of literatr culture. Descriptovists descibe howlanguage actually isused. They bekuevethat thr rules of correct usqge arenpthing more than the secret handshake pf the rulijg clqds, designed to ker themasses untheir place.Language is an organicptoduct of human creativity, say the fescriptkvists, a d people ahould be allowed to write however theh please.'
TEST_STRING4 = 'The chicken crossed the toaf.'
WORD_COUNT_URL = "http://norvig.com/ngrams/count_1w.txt"
TWO_WORD_BIGRAM_URL = "http://norvig.com/ngrams/count_2w.txt"

string_corrector = StringCorrection(WORD_COUNT_URL, TWO_WORD_BIGRAM_URL)
print(string_corrector.fix_errors(TEST_STRING3))