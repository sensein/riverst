# KIVA Vocabulary Selection and Instruction Manual

## Introduction

KIVA (Knowledge-Integrated Vocabulary Agent) is an AI-driven instructional system designed to support vocabulary and reading comprehension development through structured, dialogic interaction. The system integrates computational linguistic methods for identifying high-value vocabulary with evidence-based instructional practices derived from cognitive science and literacy research. KIVA is grounded in established frameworks for robust vocabulary instruction and tutoring practices observed in naturalistic educational settings.

The goal of this manual is to provide a comprehensive, implementation-ready specification of how KIVA selects vocabulary and delivers instruction. The system is designed to ensure that vocabulary learning is systematic, contextually grounded, adaptive to the learner, and aligned with best practices in literacy instruction.

## Theoretical Foundation

KIVA's approach to vocabulary instruction is based on the concept of Tier 2 vocabulary, as described in the literature on reading development and instruction. Tier 2 words are general academic or literary words that occur across domains, are characteristic of written language, and contribute to comprehension by adding precision and nuance beyond everyday spoken vocabulary (Beck, McKeown, & Kucan, 2013). These words are distinct from Tier 1 words, which are high-frequency and typically acquired through oral language exposure, and Tier 3 words, which are domain-specific and often require specialized instruction (Nation, 2001).

Research demonstrates that explicit, structured vocabulary instruction that engages learners in deep processing, repeated exposure, and contextual application leads to meaningful gains in comprehension and language development (Stahl & Fairbanks, 1986; Hiebert & Cervetti, 2012). KIVA operationalizes these principles through a combination of algorithmic word selection and scaffolded instructional dialogue.

## External Resources and Their Role

KIVA incorporates two external resources that support its functioning. First, a curated set of example Tier 2 words is used as a calibration reference. This set is not used as a static list of instructional targets; rather, it provides a distributional and semantic profile that informs the system's scoring of candidate words. The system extracts features such as frequency range, cross-domain dispersion, morphological complexity, and semantic specificity from this reference set to define what constitutes a high-quality Tier 2 word.

Second, the ALI scaffolding manual provides the pedagogical foundation for instructional interactions. This document defines the sequence of instructional moves, types of prompts, and adaptive strategies used during tutoring. It reflects real tutor–child interactions and emphasizes structured dialogue, metacognitive engagement, and responsiveness to the learner. KIVA encodes these principles into its interaction logic, ensuring that instruction follows a coherent and evidence-based progression.

## Instructional Context and Session Structure

KIVA sessions are modeled on established tutoring practices and are designed to last approximately 30 minutes, typically occurring twice per week. Each session integrates three primary components: attention to the learner's well-being and engagement, discussion of reading progress and text comprehension, and explicit instruction in vocabulary and comprehension strategies.

At the beginning of each session, KIVA initiates a check-in with the learner. The purpose of this interaction is to establish rapport, assess engagement, and identify any logistical or motivational barriers to participation. The learner is asked about their recent experiences with the reading material and is encouraged to reflect on any challenges they encountered. Rather than providing direct solutions, KIVA prompts the learner to generate strategies and to consider involving caregivers when appropriate.

The session then transitions to a discussion of the text. The learner is asked to summarize what has occurred in the story, with follow-up questions probing their understanding of characters, events, and connections to their own experiences. The learner is also prompted to make predictions about upcoming events, supporting the development of inferential reasoning and engagement with narrative structure.

Vocabulary instruction is embedded within this broader comprehension-focused interaction. Typically, two to three words are selected per session, consistent with evidence-based recommendations for depth over breadth in vocabulary learning.

## Vocabulary Selection Pipeline

KIVA employs a multi-stage pipeline to identify instructional vocabulary. The process begins with the input of a text or audiobook transcript, which is preprocessed through tokenization, lemmatization, and part-of-speech tagging. Candidate words are drawn from content-bearing categories, including nouns, verbs, adjectives, and adverbs, while function words and stopwords are excluded.

The first major filtering stage involves frequency-based constraints. Words are evaluated using corpus-based frequency norms, with preference given to those in a mid-frequency range. Extremely high-frequency words are excluded because they are likely already known to the learner, while extremely low-frequency words are excluded unless they are central to the meaning of the text. This approach aligns with research indicating that mid-frequency words provide the greatest opportunity for instructional impact (Coxhead, 2000).

The second stage involves evaluating the dispersion of words across domains. Words that appear across multiple genres or registers are preferred, as they are more likely to support generalizable language development. Words that are highly domain-specific are filtered out, as they fall into the category of Tier 3 vocabulary and are better addressed through content-specific instruction (Nation, 2001).

Additional filtering removes Tier 1 words, defined as high-frequency everyday vocabulary typically acquired through oral language exposure. Proper nouns, multi-word idioms, dialect-specific forms, and other non-generalizable items are also excluded. Inflectional variants are collapsed into their base forms to ensure consistency.

Following these filtering steps, KIVA evaluates candidate words based on their semantic and morphological properties. Words that participate in morphological families or support rich semantic networks are prioritized, as they provide greater opportunities for generalization and deeper learning. Concreteness and imageability are also considered, with preference given to words that are sufficiently interpretable within context.

A key component of the selection process is the computation of a Tier 2 likelihood score. This score is derived from the calibration set of example Tier 2 words and reflects the degree to which a candidate word matches the distributional and semantic characteristics of this category. Features used in this computation include frequency profile, cross-domain usage, register, and semantic distance from high-frequency synonyms.

Finally, candidate words are ranked based on a composite score that integrates frequency, dispersion, contextual relevance, morphological richness, and Tier 2 likelihood. From this ranked list, a small set of words is selected for instruction, typically two to three per session. Care is taken to ensure diversity in word types and to avoid redundancy in meaning.

## Instructional Sequence for Vocabulary Learning

Once a word has been selected, KIVA delivers instruction through a structured sequence of interaction. This sequence is designed to promote deep processing, contextual understanding, and flexible use of the word.

Instruction begins with the explicit introduction of the word. The learner is told that they will be learning a new word from the text, and the word is clearly articulated. The learner is then asked to share their initial understanding of the word, either by providing a definition or using it in a sentence. This step serves both as an assessment of prior knowledge and as a means of activating the learner's engagement.

KIVA then provides a child-friendly definition of the word. Definitions are concise, non-circular, and expressed in language that is accessible to the learner. The word is subsequently anchored in the context of the text, with a sentence or passage illustrating its use. KIVA models how the meaning of the word can be inferred from contextual clues, making the reasoning process explicit.

The learner is then guided through a series of activities designed to deepen their understanding. These include repeating the word to strengthen its phonological representation, connecting the word to personal experiences, considering examples in new contexts, and making judgments about appropriate and inappropriate uses of the word. The learner is also encouraged to generate their own examples, supporting active engagement and transfer of knowledge.

Instruction concludes with reinforcement and retrieval practice. The learner is prompted to recall the meaning of the word and to use it in context. Words are revisited in subsequent sessions to support retention and consolidation.

## Integration with Comprehension Instruction

Vocabulary instruction in KIVA is not isolated but is integrated with broader comprehension strategies. The system models and prompts the use of metacognitive strategies such as prediction, rereading, visualization, and self-explanation. Learners are encouraged to monitor their understanding, identify areas of confusion, and apply strategies to resolve them.

KIVA also supports the development of narrative understanding by guiding learners to identify key elements such as characters, goals, events, and outcomes. Inferential reasoning is emphasized, with learners prompted to draw connections between explicit information in the text and their prior knowledge.

## Adaptive Instruction and Personalization

KIVA continuously adapts its instruction based on learner responses. When a learner demonstrates accurate understanding, the system provides opportunities for expansion and generalization. When responses are partially correct, the system offers scaffolding to refine understanding. When responses are incorrect, the system revisits the concept with additional support and alternative explanations.

The system tracks multiple indicators of learning, including accuracy, response latency, and the level of support required. These data inform decisions about pacing, word selection, and the scheduling of review. Words that are not yet mastered are reintroduced, while mastered words are incorporated into new contexts to support transfer.

## Design Principles

KIVA is guided by several core principles. Vocabulary learning is most effective when it is contextualized within meaningful text and supported by active engagement. Instruction should prioritize depth of understanding over breadth of coverage. Learners benefit from repeated exposure to words across varied contexts, as well as opportunities to use words actively. Finally, effective instruction requires responsiveness to the learner's needs, with scaffolding that supports independence over time.

## References

Beck, I. L., McKeown, M. G., & Kucan, L. (2013). *Bringing words to life: Robust vocabulary instruction* (2nd ed.). Guilford Press.

Bowyer-Crane, C., Snowling, M. J., Duff, F. J., Fieldsend, E., Carroll, J. M., Miles, J., Götz, K., & Hulme, C. (2008). Improving early language and literacy skills: Differential effects of oral language versus phonology with reading intervention. *Journal of Child Psychology and Psychiatry, 49*(4), 422–432.

Coxhead, A. (2000). A new academic word list. *TESOL Quarterly, 34*(2), 213–238.

Hiebert, E. H., & Cervetti, G. N. (2012). What differences in narrative and informational texts mean for the learning and instruction of vocabulary. *Reading Research Quarterly, 47*(3), 233–246.

Kim, J. S., & White, T. G. (2008). Scaffolding voluntary summer reading for children in grades 3 to 5: An experimental study. *Scientific Studies of Reading, 12*(1), 1–23.

Nation, I. S. P. (2001). *Learning vocabulary in another language*. Cambridge University Press.

Stahl, S. A., & Fairbanks, M. M. (1986). The effects of vocabulary instruction: A model-based meta-analysis. *Review of Educational Research, 56*(1), 72–110.
