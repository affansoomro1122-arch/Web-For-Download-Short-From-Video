# WOP-001 TEST RENDER - S1, S2, S7 ONLY
Do not generate S3, S4, S5, S6, S8, S9, S10 until this test is approved.

Every prompt below = STYLE BLOCK + character references + the action text.
Attach all four character reference images to every generation.
Attach WOP-001_ref_office.png as the environment reference.
Generate native 9:16. Never crop.

--------------------------------------------------------------------
S1  (0:00-0:03)  TESTS: character consistency + environment lock
--------------------------------------------------------------------
[STYLE BLOCK]
Wide shot. Four colleagues stand together facing the camera in a small
startup office. The team lead stands centre front, closest to camera,
looking directly into the lens with a completely neutral, slightly tired
expression. Three colleagues stand behind him: one back-left, one
back-right, one back-centre and half a step further back. Nobody smiles.
Nobody moves. They are waiting for someone to tell them what to do.
Static camera. Three seconds. No dialogue.

WHAT TO CHECK: Do all four faces match the reference images? Is the office
identical to the plate? Are the positions right? Generate 3 takes.

--------------------------------------------------------------------
S2  (0:03-0:06)  TESTS: lip-sync quality - THE CRITICAL ONE
--------------------------------------------------------------------
[STYLE BLOCK]
Very slow push toward the team lead, from a group wide to a medium shot
of him alone. He speaks three words directly to camera with a flat,
serious expression. The three colleagues remain visible behind him,
motionless and unsmiling. The push is almost imperceptible.
Three seconds.

LIP-SYNC: upload WOP-001_vo_teamlead.wav, line "This is Wopie."

WHAT TO CHECK: Watch it on a phone at full size, twice. Do the mouth
shapes land on the words? Any warping around the jaw or teeth? Generate
4 takes - lip-sync is the least reliable step, so give it the most tries.

IF IT PASSES -> use lip-sync for S4 and S9 as well.
IF IT FAILS  -> restructure per the fallback in the main brief:
                start dialogue before cutting to the speaker, cover long
                lines with reaction shots and product inserts, show the
                team lead speaking only in short phrases, let the clean
                audio carry it. Never keep an obviously wrong lip-sync
                shot. A silent reaction shot always beats a broken mouth.

--------------------------------------------------------------------
S7  (0:20-0:23)  TESTS: does the comedy actually land
--------------------------------------------------------------------
[STYLE BLOCK]
Same wide group composition as S1, identical positions. All four people
produce forced, uncomfortable smiles for the camera - the smiles are
clearly fake and appear too suddenly, as if on command. The smiles do not
reach their eyes. Roughly one second later, the young man in the navy
hoodie at back-right raises an awkward, delayed thumbs-up, noticeably
after everyone else has already reacted. Nobody laughs. Nobody speaks.
Three seconds. No dialogue.

WHAT TO CHECK: Is the thumbs-up genuinely LATE? That delay is the entire
joke. If everyone reacts at once, it is not funny - it is just a photo.
Generate 5 takes and pick the most uncomfortable one. This is the beat
worth spending generations on.

--------------------------------------------------------------------
TEST VERDICT - answer these before generating anything else
--------------------------------------------------------------------
  [ ] S1: all four characters match their references, no drift
  [ ] S1: office and positions identical to the lock
  [ ] S2: lip-sync convincing on a phone at full size - YES or NO
  [ ] S7: the thumbs-up reads as clearly late
  [ ] S7: the forced smiles feel uncomfortable, not cheerful
  [ ] Overall: does this look like a real team, or like AI actors?

If any box fails, fix the lock and re-test. Do not proceed with a
"close enough" character. Drift compounds across ten scenes.
