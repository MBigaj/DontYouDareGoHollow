# Source art prompts

Each source here was generated with Figma AI (model `gpt-image-2.5-sunburst`) in the Figma file "ASHEN source art", then run through the ASHEN pipeline by `tools/sprites/ronin.py`. To redo one, generate with the same prompt, keep the composition rules below, save it here as a JPEG under the same name, and run `ronin.py`.

Rules that make a source pixelate well:

- Characters and props: the whole subject visible, centred, on a plain flat light grey background, no floor or shadow. The pipeline cuts the background out by colour.
- Strong rim light from the upper left, large simple shapes, a clear silhouette.
- No text. Image models garble kana, so glyphs such as the Warden's て are drawn in code afterwards.
- Scenes: say where each landmark sits in the frame. The atlas points are then placed on the landmarks (`hollow.domain.atlas`).

## knight.jpg (1024x1536)

Dark fantasy concept art of an original character, full body, front view, standing still and imposing: a weathered knight in dark battle-worn steel plate armor, a tall closed great helm with a narrow visor slit and a single faint ember glowing behind it, a short bone-white crest, heavy layered pauldrons with tarnished gold trim, a long tattered deep crimson cloak with torn hem flowing behind, both gauntlets resting on the pommel of a huge greatsword planted point-down in front of him between his feet. Strong warm golden rim light from the upper left, deep shadows, high contrast, clear readable silhouette, large simple shapes, painterly, epic and solemn mood. Entire figure visible from helm to boots, centered, isolated on a plain flat light grey background, no floor, no shadow, no text.

## warden.jpg (1024x1280)

Dark fantasy boss concept art of an original character, full body, front view, a towering hulking gatekeeper giant standing his ground: a deep dark hooded cowl hiding the face in black shadow with two small glowing red ember eyes, a spiked bronze circlet crown over the hood, massive layered bronze pauldrons with verdigris and rivets, an embossed bronze breastplate with a sun disc, a heavy chainmail skirt and a tattered dark cape. On his right arm (left side of the image) a huge round bronze shield with a smooth plain dark center and a studded rim. His other hand grips a colossal iron warhammer held upright at his side on the right of the image, the hammer head raised above his shoulder. Strong warm golden rim light from the upper left, deep shadows, high contrast, clear readable silhouette, large simple shapes, painterly, menacing, epic. Entire figure visible from crown to feet, centered, isolated on a plain flat light grey background, no floor, no shadow, no text.

## bonfire.jpg (1024x1280)

A broken, notched greatsword with a gold crossguard and a leather-wrapped grip planted point-down in a mound of glowing ash, embers and bones (a ribcage, a skull), ringed by rough stones, on a plain flat grey background. The original prompt was not kept; this describes the result.

## firelink.jpg (1536x864, cropped to 1498x864)

Epic dark fantasy landscape painting, wide side-on game map view, golden dusk. Composition: in the bottom-left corner a small campfire bonfire glowing warm orange on dark ground; from there a long grassy hillside rises steadily toward the upper right, with broken terraces, rocks, scattered gravestones and swords planted in the earth, and a few dead twisted trees. On the hilltop at the upper right (about one quarter from the top of the image) stands a grand ruined stone shrine: broken colonnade, a tall arched gateway filled with pale swirling white fog, and a colossal weathered statue of a hooded knight with a greatsword. In the sky at the upper left hangs a black eclipsed sun with a burning golden ring and long rays; the sky glows from deep violet at the top to fiery amber and gold at the horizon, with long dark cloud banks lit gold underneath. Far in the hazy distance on the left, jagged mountains and a slender gothic castle silhouette. Atmospheric haze, rim light, high contrast, inspired by Elden Ring and Dark Souls, painterly, majestic, no characters, no text, no UI.

## arena_firelink.jpg (1536x1024, cropped to 1536x960)

Epic dark fantasy boss arena background painting, side-on game view, empty of any characters: the courtyard of a vast ruined shrine at golden dusk. A wide flat floor of cracked ancient flagstones fills the bottom third of the image, scattered with ash, bones, broken swords and dead leaves. Behind it, colossal broken stone columns and crumbling gothic arches frame the space, a towering arched gateway filled with pale swirling fog on the left, tattered banners hanging, and through the broken roof a burning amber sky with a black eclipsed sun ringed in gold, light shafts and drifting embers in the air. Deep shadows at the edges, warm golden rim light, atmospheric haze, high contrast, inspired by Elden Ring and Dark Souls, painterly, majestic, the center and right of the floor kept open and uncluttered for the fight, no characters, no creatures, no text, no UI.

## stage.jpg (1024x1024, cropped to 1024x923)

Dark fantasy painting of an empty resting place inside a ruined stone shrine at night, straight-on side view like a 2D game backdrop. A worn floor of large cracked flagstones fills the bottom fifth of the image, flat and empty. Behind it a tall crumbling stone wall with a great broken gothic arch in the middle; through the arch a deep night sky with a pale hazy moon, faint stars and distant jagged mountains. Ivy and dead roots creep over the stones, a toppled pillar lies at the far left edge, a few old swords lean against the wall at the right edge, small candles burnt down in a niche. Mostly dark and calm, cold blue moonlight from above, the foreground floor in shadow, large simple shapes, painterly, inspired by Dark Souls and Elden Ring, solemn. The middle of the floor is completely empty and uncluttered. No characters, no fire, no bonfire, no text.

## world.jpg (1280x1024, cropped to 1183x1024)

Epic dark fantasy world map painting seen from a high three-quarter aerial view, like a game overworld, golden dusk under an eclipsed black sun with a burning gold ring in the upper middle sky. A winding ancient road with tiny glowing ember lights connects six landmarks, climbing from the bottom left to the top right: (1) bottom left corner: a small ruined hilltop shrine with a glowing campfire bonfire; (2) a little right and above it: a dark abandoned village of crooked timber houses with a few lit windows; (3) further up on the left: the dark carved stone entrance of underground catacombs in a cliff face, with skulls and pale glowing runes; (4) center: a grim stone fortress on a crag with walls and towers; (5) upper right: a radiant golden cathedral city with domes and spires catching the light; (6) top right corner: a colossal dark volcanic mountain peak with a huge pillar of fire burning at its summit. Between them mist-filled valleys, cliffs, dead forests, rivers and ruins. Rich warm amber light against deep violet shadows, atmospheric haze, high contrast, majestic and ominous, inspired by Elden Ring and Dark Souls, painterly, no text, no labels, no UI, no frame.
