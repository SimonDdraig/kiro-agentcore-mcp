# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Seed the BushRangerSightings DynamoDB table with 1000 realistic example records.

Usage:
    AWS_DEFAULT_REGION=us-east-1 python scripts/seed_sightings.py

Optionally override the table name:
    DYNAMODB_TABLE_NAME=MyTable python scripts/seed_sightings.py

The script uses batch_writer for efficient writes (25 items per batch).
It is idempotent — re-running will overwrite existing seed records
(same species + date + location → same sort key).
"""

from __future__ import annotations

import hashlib
import os
import random
import uuid

import boto3

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "BushRangerSightings")
REGION = os.environ.get("AWS_DEFAULT_REGION", os.environ.get("AWS_REGION", "us-east-1"))
TOTAL_RECORDS = 1000

# ---------------------------------------------------------------------------
# Species catalogue — 30 Australian species with realistic IUCN statuses
# ---------------------------------------------------------------------------
SPECIES = [
    ("Eastern Grey Kangaroo", "least_concern"),
    ("Red Kangaroo", "least_concern"),
    ("Koala", "vulnerable"),
    ("Platypus", "near_threatened"),
    ("Wombat", "least_concern"),
    ("Tasmanian Devil", "endangered"),
    ("Quokka", "vulnerable"),
    ("Echidna", "least_concern"),
    ("Sugar Glider", "least_concern"),
    ("Kookaburra", "least_concern"),
    ("Sulphur-crested Cockatoo", "least_concern"),
    ("Wedge-tailed Eagle", "least_concern"),
    ("Emu", "least_concern"),
    ("Saltwater Crocodile", "least_concern"),
    ("Frilled-neck Lizard", "least_concern"),
    ("Green Sea Turtle", "endangered"),
    ("Dugong", "vulnerable"),
    ("Numbat", "endangered"),
    ("Bilby", "vulnerable"),
    ("Cassowary", "vulnerable"),
    ("Leadbeater's Possum", "critically_endangered"),
    ("Orange-bellied Parrot", "critically_endangered"),
    ("Mountain Pygmy-possum", "critically_endangered"),
    ("Western Swamp Tortoise", "critically_endangered"),
    ("Spotted-tail Quoll", "near_threatened"),
    ("Brush-tailed Rock-wallaby", "vulnerable"),
    ("Black-flanked Rock-wallaby", "endangered"),
    ("Regent Honeyeater", "critically_endangered"),
    ("Swift Parrot", "critically_endangered"),
    ("Helmeted Honeyeater", "critically_endangered"),
]

# ---------------------------------------------------------------------------
# Australian locations — (name, lat, lng) covering diverse regions
# ---------------------------------------------------------------------------
LOCATIONS = [
    ("Blue Mountains NP, NSW", -33.7150, 150.3120),
    ("Kakadu NP, NT", -12.8280, 132.8830),
    ("Daintree Rainforest, QLD", -16.2500, 145.4186),
    ("Great Otway NP, VIC", -38.7500, 143.5500),
    ("Cradle Mountain, TAS", -41.6500, 145.9500),
    ("Kangaroo Island, SA", -35.7750, 137.2142),
    ("Ningaloo Reef, WA", -22.6900, 113.6800),
    ("Uluru-Kata Tjuta NP, NT", -25.3444, 131.0369),
    ("Wilsons Promontory, VIC", -39.0500, 146.3667),
    ("Lamington NP, QLD", -28.2167, 153.1333),
    ("Ku-ring-gai Chase NP, NSW", -33.6500, 151.2000),
    ("Freycinet NP, TAS", -42.1333, 148.2833),
    ("Flinders Ranges, SA", -31.3333, 138.6333),
    ("Litchfield NP, NT", -13.1500, 130.7833),
    ("Noosa NP, QLD", -26.3833, 153.1000),
    ("Grampians NP, VIC", -37.1500, 142.4000),
    ("Stirling Range NP, WA", -34.3833, 118.0667),
    ("Jervis Bay, NSW", -35.0833, 150.7000),
    ("Cape Tribulation, QLD", -16.1000, 145.4667),
    ("Rottnest Island, WA", -32.0000, 115.5167),
]

# ---------------------------------------------------------------------------
# Species-specific observer notes — biologically accurate for each species
# ---------------------------------------------------------------------------
SPECIES_NOTES: dict[str, list[str]] = {
    "Eastern Grey Kangaroo": [
        "Mob of 8 grazing on open grassland at dawn. Several joeys visible in pouches.",
        "Single adult male resting under eucalyptus shade. Muscular build, estimated 60kg.",
        "Group of 12 moving through woodland edge at dusk. Bounding gait, heading toward waterhole.",
        "Female with large joey peeking from pouch, grazing near creek bed. Calm and undisturbed.",
        "Two males engaged in boxing match on open ground. Sparring lasted several minutes.",
        "Mob scattered when approached — powerful leaps covering 5-6 metres each bound.",
        "Juvenile grazing independently near the mob. Appears recently left the pouch.",
        "Adult resting in prone position during midday heat. Licking forearms to cool down.",
        "Roadside sighting — mob of 5 crossing at dusk. Moved quickly into scrub.",
        "Large male standing upright, alert posture, ears rotating. Sentinel behaviour observed.",
    ],
    "Red Kangaroo": [
        "Large male (estimated 80kg) resting in shade of mulga scrub. Distinctive red-brown fur.",
        "Small mob of 6 grazing on arid grassland at dawn. Moved slowly across open plain.",
        "Female with joey in pouch hopping across red dirt track. Joey's head and feet visible.",
        "Two males sparring — leaning back on tails and kicking with hind legs.",
        "Mob of 10 sheltering under sparse trees during midday heat. Minimal movement.",
        "Single adult bounding across open plain at speed — estimated 40km/h.",
        "Group drinking at artificial waterhole. Took turns approaching cautiously.",
        "Adult male licking forearms repeatedly — thermoregulation behaviour in 38°C heat.",
        "Female grazing with well-furred joey hopping alongside. Joey still nursing occasionally.",
        "Mob resting in shallow depression in red soil. Ears twitching, alert to surroundings.",
    ],
    "Koala": [
        "Single adult wedged in fork of large eucalyptus, sleeping. Typical daytime resting posture.",
        "Female with back-young clinging to her shoulders, moving between branches at dusk.",
        "Adult male bellowing from high branch — deep grunting vocalisation carried across the valley.",
        "Koala feeding on Eucalyptus viminalis leaves. Slow, deliberate chewing observed.",
        "Solitary individual descending tree trunk at dusk, likely moving to a new feeding tree.",
        "Mother and joey spotted — joey riding on mother's back through eucalyptus canopy.",
        "Adult resting motionless in tree fork for over 2 hours. Typical energy-conserving behaviour.",
        "Signs of chlamydia — wet, stained fur around rump. Reported to wildlife rescue.",
        "Koala crossing road at ground level after dark. Slow, vulnerable movement.",
        "Healthy adult feeding actively on new-growth eucalyptus tips. Good body condition.",
    ],
    "Platypus": [
        "Single individual foraging in shallow creek at dawn. Diving repeatedly, surfacing to chew prey.",
        "Platypus swimming upstream with characteristic low profile — only bill and head visible.",
        "Observed entering burrow in creek bank. Entrance just above waterline, partially concealed by roots.",
        "Foraging in still pool — bill sweeping side to side along muddy bottom. Electroreception hunting.",
        "Surfaced with crayfish in bill. Chewed at surface for 30 seconds before diving again.",
        "Two individuals foraging in same stretch of creek. Maintained 10m distance from each other.",
        "Platypus grooming on partially submerged log. Using hind feet to clean dense fur.",
        "Spotted during nocturnal survey — active in creek pool under spotlight at 9pm.",
        "Bubble trail visible before surfacing. Dove for approximately 40 seconds per foraging dive.",
        "Adult male — venomous spur visible on hind leg. Healthy, active foraging behaviour.",
    ],
    "Wombat": [
        "Single common wombat grazing on grass near burrow entrance at dusk. Stocky, healthy build.",
        "Fresh cube-shaped droppings found on elevated rock near burrow. Wombat emerged shortly after.",
        "Adult wombat crossing fire trail at twilight. Characteristic waddle gait, unhurried.",
        "Burrow system identified — multiple entrances in sandy hillside. Scratch marks on nearby trees.",
        "Wombat grazing on native grasses in open clearing. Paused to scratch against tree trunk.",
        "Nocturnal survey — wombat foraging on sedges near creek. Moved away slowly when spotlighted.",
        "Mother with small joey following closely. Joey still small, staying within a metre of mother.",
        "Large adult resting just inside burrow entrance. Nose and ears visible from 5m away.",
        "Wombat digging vigorously — extending existing burrow. Soil being kicked out behind.",
        "Roadside sighting at dusk. Wombat grazing on roadside grass, moved into bush when car slowed.",
    ],
    "Tasmanian Devil": [
        "Single devil feeding on wallaby carcass at night. Powerful jaw crunching through bone audible from 20m.",
        "Two devils in aggressive confrontation — loud screeching and gaping threat displays.",
        "Devil detected via spotlight — eyes reflected bright red. Foraging along forest track.",
        "Scat found containing fur, bone fragments, and feathers. Devil spotted nearby shortly after.",
        "Juvenile devil foraging alone in undergrowth. Smaller build, likely recently independent.",
        "Adult devil trotting along forest road at night. Stocky build, characteristic loping gait.",
        "Devil at communal latrine site. Multiple scats present — territory marking behaviour.",
        "Checked for facial tumour disease — this individual appeared healthy, no visible lesions.",
        "Devil investigating fallen log, sniffing intensely. Likely detecting invertebrate prey.",
        "Camera trap captured devil carrying prey item back to den. Nocturnal activity confirmed.",
    ],
    "Quokka": [
        "Group of 4 quokkas grazing on low vegetation near walking track. Unfazed by human presence.",
        "Single quokka resting in shade of dense shrub during midday heat. Panting slightly.",
        "Quokka hopping along boardwalk at dusk. Characteristic small, rounded body and short tail.",
        "Female with tiny joey visible in pouch. Grazing on succulent leaves near settlement area.",
        "Quokka feeding on fallen leaves and bark. Used forepaws to manipulate food items.",
        "Group sheltering under dense Rottnest Island tea-tree during hot afternoon.",
        "Quokka drinking from freshwater soak. Lapped water cautiously, alert to surroundings.",
        "Nocturnal survey — 6 quokkas active on grassy area near accommodation. Social foraging.",
        "Single quokka climbing low shrub to reach fresh leaf growth. Agile despite stocky build.",
        "Quokka resting in shallow scrape under bush. Typical daytime shelter behaviour.",
    ],
    "Echidna": [
        "Single echidna digging into termite mound with powerful forelimbs. Long tongue visible.",
        "Echidna curled into defensive ball when approached — spines fully erect.",
        "Slow-moving echidna crossing bush track. Characteristic waddling gait, nose to ground.",
        "Echidna foraging in leaf litter, using long snout to probe for ants. Tongue flicking rapidly.",
        "Found partially buried in soft soil — digging-in defence behaviour when disturbed.",
        "Echidna train observed — single female followed by 3 males in breeding season procession.",
        "Adult echidna swimming across shallow creek. Snout held above water as snorkel.",
        "Echidna resting in hollow log during heat of day. Spines visible at entrance.",
        "Fresh diggings in soil — conical holes typical of echidna foraging for invertebrates.",
        "Echidna moving through undergrowth at dawn. Paused frequently to sniff and probe soil.",
    ],
    "Sugar Glider": [
        "Sugar glider spotted gliding between trees at dusk — estimated 30m glide distance.",
        "Pair of sugar gliders emerging from tree hollow at sunset. Membrane visible when stretching.",
        "Nocturnal survey — sugar glider feeding on acacia gum. Licking sap from scored bark.",
        "Heard characteristic yapping call before visual sighting. Glider in eucalyptus canopy.",
        "Sugar glider landing on tree trunk after glide. Gripped bark with sharp claws.",
        "Group of 4 in communal nest hollow. Huddled together, likely for warmth.",
        "Sugar glider catching moths in flight during spotlight survey. Agile aerial manoeuvres.",
        "Sap-feeding scars on eucalyptus trunk — V-shaped incisions typical of sugar glider activity.",
        "Single glider foraging for insects under loose bark. Using long fingers to extract prey.",
        "Sugar glider vocalisation heard — short barking calls from canopy. Two individuals located.",
    ],
    "Kookaburra": [
        "Laughing kookaburra calling from dead branch at dawn. Full territorial laugh, joined by mate.",
        "Kookaburra swooped from perch to catch skink on ground. Bashed prey on branch before swallowing.",
        "Pair perched together on power line. Mutual preening observed — bonded pair.",
        "Kookaburra watching ground intently from low branch. Hunting posture, head tilted.",
        "Family group of 4 calling in chorus at dusk. Territorial boundary display.",
        "Single kookaburra with large insect in bill. Flew to nest hollow in eucalyptus.",
        "Kookaburra bathing in shallow puddle on track. Vigorous splashing and wing-flapping.",
        "Observed kookaburra dropping snail onto rock repeatedly to break shell. Tool-use behaviour.",
        "Juvenile kookaburra begging from adult. Fluttering wings and calling — still being fed.",
        "Kookaburra perched silently, scanning leaf litter. Pounced on beetle after 3-minute wait.",
    ],
    "Sulphur-crested Cockatoo": [
        "Flock of 30+ cockatoos feeding on grass seeds in park. Loud screeching contact calls.",
        "Single cockatoo stripping bark from eucalyptus branch. Powerful bill making short work of wood.",
        "Pair displaying — crests raised, head-bobbing, and mutual preening on dead branch.",
        "Cockatoo flock roosting in tall eucalyptus at dusk. Noisy settling-in calls for 20 minutes.",
        "Juvenile cockatoo practising flight between trees. Slightly clumsy landings.",
        "Cockatoo using foot to hold seed pod while extracting seeds with bill. Dexterous feeding.",
        "Flock of 50 wheeling overhead in late afternoon. Heading toward communal roost site.",
        "Single cockatoo hanging upside-down from branch, playing. Typical intelligent behaviour.",
        "Cockatoo excavating nest hollow in large dead eucalyptus. Wood chips falling below.",
        "Rain-bathing behaviour — cockatoo hanging with wings spread in light shower. Crest raised.",
    ],
    "Wedge-tailed Eagle": [
        "Adult eagle soaring on thermals at 500m+ altitude. Distinctive wedge-shaped tail visible.",
        "Pair of wedge-tailed eagles circling together. Aerial courtship display with talon-locking.",
        "Eagle perched on dead tree scanning open grassland. Launched into hunting dive.",
        "Wedge-tailed eagle feeding on roadkill kangaroo. Reluctant to leave, hopped away when car approached.",
        "Juvenile eagle (brown plumage) perched on fence post. Lighter colouring than adult.",
        "Eagle carrying rabbit in talons, flying toward ridge. Nest likely on cliff ledge.",
        "Two eagles mobbed by magpies near nest site. Eagles largely ignored the harassment.",
        "Large stick nest spotted in tall eucalyptus. Adult eagle sitting — likely incubating.",
        "Eagle stooping on brown hare in open paddock. Successful strike, carried prey to perch.",
        "Soaring eagle with 2.3m wingspan casting shadow on ground. Magnificent sight.",
    ],
    "Emu": [
        "Group of 5 emus walking across open grassland. Long strides, necks swaying rhythmically.",
        "Male emu with 8 striped chicks following closely. Father guarding attentively.",
        "Single emu drinking at farm dam. Dipped bill and tilted head back to swallow.",
        "Emu running across paddock at speed — estimated 45km/h. Powerful legs in full stride.",
        "Pair of emus foraging in crop stubble. Pecking at fallen grain and insects.",
        "Emu dust-bathing in dry patch of ground. Rolling and fluffing loose feathers.",
        "Male emu sitting on nest — large dark green eggs visible. Incubation duty observed.",
        "Emu feeding on native fruits and seeds along bush track. Swallowed small stones for gizzard.",
        "Roadside sighting — emu standing near fence line, watching traffic. Did not flee.",
        "Group of 3 juvenile emus (no stripes) foraging independently. Nearly adult size.",
    ],
    "Saltwater Crocodile": [
        "Large saltwater croc (estimated 4.5m) basking on muddy riverbank. Mouth agape for thermoregulation.",
        "Crocodile eyes and nostrils visible at water surface. Motionless, ambush posture in tidal creek.",
        "Slide marks on riverbank indicating large crocodile entry point. Fresh tracks in mud.",
        "Juvenile croc (approx 1m) spotted in mangrove-lined creek. Fled into water when detected.",
        "Adult crocodile performing high walk across mudflat at low tide. Impressive size and power.",
        "Crocodile nest mound found in vegetation above high-water mark. Female likely guarding nearby.",
        "Large croc lunged at fish near boat ramp. Explosive strike from still water.",
        "Saltwater crocodile floating downstream with current. Only scutes of back visible above water.",
        "Hatchling crocodiles (approx 30cm) spotted in shallow backwater. High-pitched chirping calls.",
        "Crocodile trap checked — 3.2m male captured for relocation from populated area.",
    ],
    "Frilled-neck Lizard": [
        "Frilled-neck lizard displaying full frill on tree trunk. Mouth open, hissing at perceived threat.",
        "Lizard sprinting bipedally across open ground to reach next tree. Characteristic upright run.",
        "Adult frilled-neck basking on fallen log in morning sun. Frill folded flat against neck.",
        "Lizard hunting insects on tree trunk. Quick tongue strike to capture ant.",
        "Frilled-neck lizard camouflaged against bark — only detected when it moved.",
        "Male displaying to rival — frill fully extended, body inflated, bobbing head aggressively.",
        "Lizard descending tree headfirst to forage on ground. Alert posture, scanning for predators.",
        "Juvenile frilled-neck (approx 15cm) spotted on sapling. Miniature frill already visible.",
        "Frilled-neck lizard catching grasshopper on ground. Returned to tree trunk immediately after.",
        "Pair observed on same tree — male larger with brighter colouring. Breeding season activity.",
    ],
    "Green Sea Turtle": [
        "Adult green turtle surfacing to breathe near reef edge. Smooth, oval carapace approx 1m.",
        "Turtle grazing on seagrass bed in shallow lagoon. Slow, methodical feeding on Halophila.",
        "Female green turtle nesting on beach at night. Digging egg chamber with rear flippers.",
        "Hatchlings emerging from nest at dawn — approximately 80 tiny turtles scrambling toward ocean.",
        "Green turtle resting on sandy bottom at 5m depth. Tucked under coral ledge.",
        "Turtle with satellite tag on carapace — part of migration tracking study.",
        "Juvenile green turtle feeding on algae-covered rocks in tidal pool. Carapace approx 40cm.",
        "Adult turtle swimming gracefully over reef. Powerful front flipper strokes, gliding motion.",
        "Nesting tracks found on beach at dawn — distinctive tractor-like pattern in sand.",
        "Green turtle with fibropapillomatosis tumours observed. Reported to marine wildlife authority.",
    ],
    "Dugong": [
        "Dugong surfacing to breathe in shallow seagrass bay. Rounded snout and split tail visible.",
        "Mother dugong with calf swimming in tandem. Calf staying close to mother's flank.",
        "Dugong feeding trail visible in seagrass bed — characteristic furrows in sandy bottom.",
        "Single dugong resting on bottom in 3m of clear water. Slow, rhythmic breathing at surface.",
        "Group of 4 dugongs in seagrass meadow. Largest estimated at 3m length, 400kg.",
        "Dugong surfacing every 3-4 minutes. Gentle exhalation audible from boat at 20m distance.",
        "Aerial survey spotted 12 dugongs in bay. Concentrated in dense Zostera seagrass patches.",
        "Dugong rolling at surface — possible social or skin-cleaning behaviour.",
        "Calf nudging mother's flank — nursing behaviour observed in shallow protected waters.",
        "Dugong avoiding boat by diving to bottom. Remained submerged for 6 minutes.",
    ],
    "Numbat": [
        "Single numbat foraging in wandoo woodland. Digging into soil with forepaws to reach termites.",
        "Numbat's long sticky tongue visible as it probed termite gallery in fallen log.",
        "Adult numbat sunbathing on log in morning. Distinctive russet and white-striped coat.",
        "Numbat moving quickly between logs, nose to ground. Covering large area while foraging.",
        "Camera trap captured numbat entering hollow log — likely using it as shelter.",
        "Numbat alert and upright on hind legs, scanning for predators. Tail raised as alarm posture.",
        "Fresh numbat diggings found — shallow scrapes in soil near termite-infested wood.",
        "Numbat foraging in open during daylight — one of few diurnal marsupials. Active at midday.",
        "Juvenile numbat spotted near adult. Smaller, slightly less defined stripe pattern.",
        "Numbat retreated into hollow log when wedge-tailed eagle shadow passed overhead.",
    ],
    "Bilby": [
        "Bilby detected during spotlight survey. Long ears and silky grey fur distinctive.",
        "Fresh bilby burrow found — deep spiral entrance in sandy soil. Characteristic shape.",
        "Bilby foraging with long snout probing soil for insect larvae. Nocturnal activity at 10pm.",
        "Bilby digging for seeds and bulbs in spinifex grassland. Rapid forepaw excavation.",
        "Single bilby hopping along sandy track at night. Long tail with white tip visible.",
        "Bilby burrow system with multiple entrances. Fresh diggings indicate active use.",
        "Bilby feeding on witchetty grubs extracted from root system. Long tongue assisting.",
        "Camera trap image of bilby carrying nesting material into burrow. Grass and leaves in mouth.",
        "Bilby tracks in soft sand — distinctive long hind foot prints with tail drag mark.",
        "Female bilby with pouch bulge — likely carrying young. Rear-opening pouch keeps dirt out while digging.",
    ],
    "Cassowary": [
        "Adult southern cassowary crossing rainforest track. Massive bird, estimated 1.7m tall, 60kg.",
        "Cassowary feeding on fallen quandong fruits. Swallowing whole fruits, important seed disperser.",
        "Male cassowary with 3 striped chicks following. Father sole carer, protective behaviour.",
        "Cassowary casque (helmet) clearly visible — large, prominent, grey-brown keratinous structure.",
        "Cassowary droppings found on track — large, containing whole seeds from rainforest fruits.",
        "Adult cassowary drinking from rainforest stream. Dipped bill and tilted head to swallow.",
        "Cassowary vocalisation heard — deep booming rumble resonating through rainforest.",
        "Cassowary standing motionless in dense undergrowth. Blue and red neck colouring vivid.",
        "Warning signs posted — cassowary crossing area. Adult spotted foraging near road edge.",
        "Juvenile cassowary (brown plumage, small casque) foraging alone. Recently independent.",
    ],
    "Leadbeater's Possum": [
        "Leadbeater's possum detected in spotlight survey — emerged from hollow in large mountain ash.",
        "Pair of Leadbeater's possums foraging on tree trunk. Licking acacia gum from bark wounds.",
        "Characteristic high-pitched chattering call heard from old-growth mountain ash canopy.",
        "Leadbeater's possum nest hollow identified in large dead stag. Critical habitat tree marked.",
        "Single individual leaping between branches in mountain ash forest. Agile, rapid movement.",
        "Leadbeater's possum feeding on insects under bark. Using long fingers to extract prey.",
        "Camera trap confirmed Leadbeater's possum using artificial nest box. Conservation success.",
        "Possum detected by call playback survey. Responded with territorial chattering.",
        "Leadbeater's possum grooming on branch. Dense, soft grey fur with distinctive dark dorsal stripe.",
        "Survey of hollow-bearing trees — 3 potential Leadbeater's possum den trees identified.",
    ],
    "Orange-bellied Parrot": [
        "Single orange-bellied parrot feeding on saltmarsh seeds at coastal site. Bright green with orange belly patch.",
        "Pair of orange-bellied parrots in low coastal scrub. Feeding on Sarcocornia seeds.",
        "Orange-bellied parrot call identified — distinctive buzzing flight call overhead.",
        "Critically endangered — one of fewer than 50 wild individuals. Banded bird, ID reported.",
        "Orange-bellied parrot foraging on beach strand-line vegetation. Picking seeds from dried plants.",
        "Flock of 3 orange-bellied parrots at known wintering site. Feeding on sedge seeds.",
        "Orange-bellied parrot using supplementary feeding station. Sunflower seeds provided by recovery program.",
        "Bird observed preening on low perch in saltmarsh. Belly patch colour confirmed identification.",
        "Orange-bellied parrot in flight — rapid wingbeats, direct flight path along coastline.",
        "Wintering survey — 2 orange-bellied parrots confirmed at this site. GPS location recorded for monitoring.",
    ],
    "Mountain Pygmy-possum": [
        "Mountain pygmy-possum captured in Elliott trap during alpine survey. Weighed 42g, healthy condition.",
        "Possum detected in boulder field at 1600m elevation. Emerged from rock crevice at dusk.",
        "Mountain pygmy-possum feeding on Bogong moth. Key high-fat food source during summer.",
        "Nest of shredded bark found in rock crevice — characteristic mountain pygmy-possum shelter.",
        "Possum torpid in hibernation survey — body temperature near ambient. Winter dormancy confirmed.",
        "Mountain pygmy-possum moving through boulder field. Tiny (12cm body), grey-brown fur.",
        "Camera trap at ski resort captured pygmy-possum using wildlife crossing tunnel. Infrastructure working.",
        "Female mountain pygmy-possum with 4 pouch young detected during spring survey.",
        "Possum feeding on seeds and berries in alpine heath. Caching food in rock crevices for winter.",
        "Mountain pygmy-possum habitat assessment — boulder field with deep crevices, suitable hibernation sites.",
    ],
    "Western Swamp Tortoise": [
        "Western swamp tortoise active in seasonal swamp after winter rains. Swimming in shallow water.",
        "Tortoise basking on mud bank at edge of ephemeral wetland. Flat, dark carapace absorbing heat.",
        "Juvenile western swamp tortoise (carapace 5cm) found during monitoring survey. Recruitment confirmed.",
        "Tortoise aestivating in clay burrow during dry summer. Located via radio transmitter.",
        "Western swamp tortoise feeding on tadpoles and aquatic invertebrates in shallow pool.",
        "Tortoise moving overland between seasonal wetlands. Slow but determined, covering 50m in 30 minutes.",
        "Captive-bred tortoise released at translocation site. Microchip ID recorded, monitoring ongoing.",
        "Western swamp tortoise courtship observed — male pursuing female in shallow water.",
        "Nest site found — 3 hard-shelled eggs buried in sandy soil above waterline.",
        "Tortoise health check — carapace measured at 13cm, weight 380g. Good body condition.",
    ],
    "Spotted-tail Quoll": [
        "Spotted-tail quoll detected on camera trap at night. Distinctive white spots on brown fur and tail.",
        "Quoll scat found on elevated rock — communal latrine site. Contains fur and bone fragments.",
        "Large male quoll (approx 4kg) crossing forest track at night. Powerful, confident gait.",
        "Quoll den identified in rock crevice. Fur and prey remains at entrance.",
        "Spotted-tail quoll climbing tree trunk at night. Hunting for possums in canopy.",
        "Female quoll with 5 young attached in pouch. Detected during trapping survey.",
        "Quoll feeding on brushtail possum carcass. Aggressive feeding, growling when spotlight shone.",
        "Quoll tracks in soft mud near creek — distinctive five-toed prints with claw marks.",
        "Spotted-tail quoll vocalisation — hissing and screeching during territorial dispute.",
        "Camera trap sequence showing quoll investigating and entering hollow log den.",
    ],
    "Brush-tailed Rock-wallaby": [
        "Group of 4 rock-wallabies on cliff face at dawn. Incredible agility on near-vertical rock.",
        "Rock-wallaby sunbathing on ledge. Brush-tipped tail curled, distinctive dark stripe on face.",
        "Juvenile rock-wallaby practising jumps between boulders. Building confidence on rocky terrain.",
        "Rock-wallaby feeding on ferns and grasses growing from rock crevices. Balanced on narrow ledge.",
        "Supplementary feeding station checked — rock-wallabies accessing food. Fox control ongoing.",
        "Rock-wallaby colony count — 7 individuals observed on cliff face during dawn survey.",
        "Female rock-wallaby with joey at foot. Joey staying close on rocky ledge.",
        "Rock-wallaby retreated into cave when wedge-tailed eagle soared overhead. Predator avoidance.",
        "Fresh rock-wallaby droppings on ledge. Colony actively using this cliff section.",
        "Rock-wallaby grooming on sun-warmed boulder. Thick, soft fur in good condition.",
    ],
    "Black-flanked Rock-wallaby": [
        "Single black-flanked rock-wallaby spotted on granite outcrop at dusk. Dark flanks distinctive.",
        "Group of 3 on rocky hillside. Feeding on grasses between boulders in fading light.",
        "Rock-wallaby sheltering in deep rock crevice during midday heat. Only ears visible.",
        "Black-flanked rock-wallaby bounding across rock face with remarkable agility. Rubber-soled feet gripping.",
        "Fresh droppings on rock ledge — colony presence confirmed at this site.",
        "Camera trap captured rock-wallaby drinking from rock pool after rain. Rare water source.",
        "Female with joey visible in pouch. Resting on sheltered ledge out of wind.",
        "Predator control bait station checked near colony. No fox activity detected this month.",
        "Rock-wallaby vocalisation — soft clicking sounds between individuals on adjacent rocks.",
        "Population survey — 5 individuals counted at this outcrop. Stable from last count.",
    ],
    "Regent Honeyeater": [
        "Single regent honeyeater feeding on ironbark nectar. Black and yellow plumage, distinctive scalloped pattern.",
        "Regent honeyeater song heard — but unusually, mimicking friarbird calls. Song loss documented.",
        "Pair of regent honeyeaters in flowering mugga ironbark. Aggressive defence of nectar resource.",
        "Critically endangered — fewer than 300 wild birds. Banded individual, ID reported to recovery team.",
        "Regent honeyeater nest found in mistletoe clump. Female incubating, male guarding nearby.",
        "Honeyeater feeding on lerp (insect secretion) on eucalyptus leaves. Supplementing nectar diet.",
        "Captive-bred regent honeyeater identified by colour bands. Released 6 months ago, surviving well.",
        "Regent honeyeater chasing noisy miners from flowering tree. Defending critical food source.",
        "Flock of 3 regent honeyeaters at key breeding site. Highest count here in 2 years.",
        "Regent honeyeater foraging in box-ironbark woodland. Probing flowers with curved bill.",
    ],
    "Swift Parrot": [
        "Swift parrot feeding on Eucalyptus globulus nectar. Fast, direct flight between trees.",
        "Flock of 8 swift parrots in flowering blue gum plantation. Chattering contact calls.",
        "Swift parrot nest hollow found in old eucalyptus. Female inside, male feeding nearby.",
        "Critically endangered — estimated fewer than 750 wild birds. Sugar glider predation a key threat.",
        "Swift parrot in rapid flight — red face and underwing patches visible. Distinctive silhouette.",
        "Pair of swift parrots feeding on eucalyptus lerp. Tongues lapping insect secretions from leaves.",
        "Swift parrot vocalisation — sharp, metallic 'kik-kik-kik' in flight. Located flock by call.",
        "Swift parrot at nest box with predator guard installed. Conservation measure working.",
        "Flock moving between flowering eucalyptus patches. Nomadic behaviour following nectar flow.",
        "Swift parrot foraging on psyllid insects on eucalyptus leaves. Important protein source.",
    ],
    "Helmeted Honeyeater": [
        "Helmeted honeyeater feeding on nectar in swamp gum. Distinctive yellow helmet crest raised.",
        "Pair of helmeted honeyeaters defending territory. Aggressive chasing of other honeyeaters.",
        "Helmeted honeyeater nest found in paperbark thicket. Woven cup nest, 2 eggs visible.",
        "Critically endangered — fewer than 200 wild birds. Colour-banded individual identified.",
        "Helmeted honeyeater feeding on manna (sap exudate) on eucalyptus trunk. Licking with brush tongue.",
        "Family group of 4 helmeted honeyeaters in riparian vegetation. Fledglings begging from adults.",
        "Helmeted honeyeater bathing in shallow creek. Vigorous splashing, then preening on low branch.",
        "Supplementary feeding station visited by 3 helmeted honeyeaters. Sugar water provided.",
        "Helmeted honeyeater song — rich, melodious warbling from dense swamp gum canopy.",
        "Habitat restoration site — newly planted swamp gums attracting helmeted honeyeaters. Positive sign.",
    ],
}


def _make_sort_key(date_iso: str, latitude: float, longitude: float) -> str:
    """Replicate the sort key logic from the MCP server."""
    loc_hash = hashlib.md5(f"{latitude},{longitude}".encode(), usedforsecurity=False).hexdigest()[:8]
    return f"{date_iso}#{loc_hash}"


def _random_note(species_name: str) -> str:
    """Return a biologically accurate observer note for the given species."""
    return random.choice(SPECIES_NOTES[species_name])


def _random_date() -> str:
    """Generate a random ISO date between 2024-01-01 and 2026-03-29."""
    from datetime import date, timedelta
    d = date(2024, 1, 1) + timedelta(days=random.randint(0, 818))
    return d.isoformat()


def _jitter(base: float, spread: float = 0.5) -> float:
    """Add random jitter to a coordinate so sightings cluster near a location."""
    return round(base + random.uniform(-spread, spread), 4)


def generate_sightings() -> list[dict]:
    """Generate 1000 sighting records."""
    records = []
    for _ in range(TOTAL_RECORDS):
        species_name, conservation_status = random.choice(SPECIES)
        loc_name, base_lat, base_lng = random.choice(LOCATIONS)
        lat = _jitter(base_lat)
        lng = _jitter(base_lng)
        date_str = _random_date()
        sighting_id = str(uuid.uuid4())
        sort_key = _make_sort_key(date_str, lat, lng)

        records.append({
            "species": species_name,
            "date_location": sort_key,
            "sighting_id": sighting_id,
            "latitude": str(lat),
            "longitude": str(lng),
            "date": date_str,
            "conservation_status": conservation_status,
            "observer_notes": _random_note(species_name),
        })
    return records


def main() -> None:
    """Seed the DynamoDB table."""
    print(f"Seeding {TOTAL_RECORDS} sightings into {TABLE_NAME} ({REGION})...")

    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    table = dynamodb.Table(TABLE_NAME)

    records = generate_sightings()

    with table.batch_writer() as batch:
        for i, record in enumerate(records, 1):
            batch.put_item(Item=record)
            if i % 100 == 0:
                print(f"  Written {i}/{TOTAL_RECORDS}...")

    print(f"Done — {TOTAL_RECORDS} sightings seeded.")

    # Print a quick summary
    species_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for r in records:
        species_counts[r["species"]] = species_counts.get(r["species"], 0) + 1
        status_counts[r["conservation_status"]] = status_counts.get(r["conservation_status"], 0) + 1

    print(f"\nSpecies distribution ({len(species_counts)} species):")
    for sp, count in sorted(species_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"  {sp}: {count}")
    print(f"  ... and {len(species_counts) - 10} more")

    print(f"\nConservation status distribution:")
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()
