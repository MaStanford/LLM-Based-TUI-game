FACTION_DATA = {   'crimson_litany': {   'control': 55,
                          'description': 'Fanatical crusaders who believe the '
                                         "engine's holy fire must be carried "
                                         'to every corner of the wasteland by '
                                         'force.',
                          'faction_boss': {   'damage_multiplier': 2.5,
                                              'hp_multiplier': 5.0,
                                              'name': 'Archdeacon Moltov',
                                              'vehicle': 'WarRig'},
                          'hub_city_coordinates': (-5, 4),
                          'name': 'The Crimson Litany',
                          'relationships': {   'iron_choir': 'Hostile',
                                               'rust_prophets': 'Hostile',
                                               'sanctum_eternal': 'Neutral',
                                               'shattered_glass_order': 'Wary'},
                          'unit_names': {   'MuscleCar': {   'description': 'Flame-painted '
                                                                            'interceptor '
                                                                            'that '
                                                                            'leads '
                                                                            'the '
                                                                            'crusade '
                                                                            'at '
                                                                            'full '
                                                                            'throttle.',
                                                             'name': 'Burning '
                                                                     'Sermon'},
                                            'RustBucket': {   'description': 'Suicide '
                                                                             'ram '
                                                                             'packed '
                                                                             'with '
                                                                             'fuel, '
                                                                             'driven '
                                                                             'by '
                                                                             'willing '
                                                                             'zealots.',
                                                              'name': "Martyr's "
                                                                      'Pyre'},
                                            'Technical': {   'description': 'Gun-truck '
                                                                            'belching '
                                                                            'holy '
                                                                            'smoke '
                                                                            'from '
                                                                            'exhaust-pipe '
                                                                            'incense '
                                                                            'burners.',
                                                             'name': 'Censer '
                                                                     'Wagon'}},
                          'units': ['MuscleCar', 'Technical', 'RustBucket']},
    'iron_choir': {   'control': 50,
                      'description': 'A militant order whose engines roar in '
                                     'rehearsed harmony, believing vehicular '
                                     'combat is the highest form of hymn.',
                      'faction_boss': {   'damage_multiplier': 2.5,
                                          'hp_multiplier': 5.0,
                                          'name': 'Cantor Ironthroat',
                                          'vehicle': 'WarRig'},
                      'hub_city_coordinates': (5, -4),
                      'name': 'The Iron Choir',
                      'relationships': {   'crimson_litany': 'Hostile',
                                           'rust_prophets': 'Wary',
                                           'sanctum_eternal': 'Neutral',
                                           'shattered_glass_order': 'Friendly'},
                      'unit_names': {   'GuardTruck': {   'description': 'Rumbling '
                                                                         'fortress '
                                                                         'truck '
                                                                         'whose '
                                                                         'idle '
                                                                         'thrums '
                                                                         'like '
                                                                         'a '
                                                                         'pipe '
                                                                         'organ.',
                                                          'name': 'Bass '
                                                                  'Bastion'},
                                        'MuscleCar': {   'description': 'High-revving '
                                                                        'interceptor '
                                                                        'tuned '
                                                                        'to '
                                                                        'scream '
                                                                        'a '
                                                                        'perfect '
                                                                        'war '
                                                                        'note.',
                                                         'name': 'Tenor Fang'},
                                        'Technical': {   'description': 'Gun-truck '
                                                                        'firing '
                                                                        'in '
                                                                        'rhythmic '
                                                                        'bursts '
                                                                        'synchronized '
                                                                        'to '
                                                                        'engine '
                                                                        'tempo.',
                                                         'name': 'Canticle '
                                                                 'Gun'}},
                      'units': ['MuscleCar', 'GuardTruck', 'Technical']},
    'rust_prophets': {   'control': 40,
                         'description': 'Wandering preachers who see corrosion '
                                        'as divine transfiguration, believing '
                                        'all metal must return to sacred dust.',
                         'faction_boss': {   'damage_multiplier': 2.0,
                                             'hp_multiplier': 5.5,
                                             'name': 'Prophet Oxus the '
                                                     'Corroded',
                                             'vehicle': 'WarRig'},
                         'hub_city_coordinates': (-4, -5),
                         'name': 'The Rust Prophets',
                         'relationships': {   'crimson_litany': 'Hostile',
                                              'iron_choir': 'Wary',
                                              'sanctum_eternal': 'Neutral',
                                              'shattered_glass_order': 'Hostile'},
                         'unit_names': {   'RaiderBuggy': {   'description': 'Corroded '
                                                                             'buggy '
                                                                             'held '
                                                                             'together '
                                                                             'by '
                                                                             'faith '
                                                                             'and '
                                                                             'tetanus.',
                                                              'name': 'Oxide '
                                                                      'Flea'},
                                           'RustBucket': {   'description': 'Volatile '
                                                                            'wreck '
                                                                            'that '
                                                                            'detonates, '
                                                                            'spreading '
                                                                            'blessed '
                                                                            'rust '
                                                                            'shrapnel '
                                                                            'everywhere.',
                                                             'name': 'Spore of '
                                                                     'Decay'},
                                           'RustySedan': {   'description': 'Decaying '
                                                                            'sedan '
                                                                            'whose '
                                                                            'body '
                                                                            'panels '
                                                                            'shed '
                                                                            'like '
                                                                            'molting '
                                                                            'skin.',
                                                             'name': 'Flaking '
                                                                     'Apostle'},
                                           'Technical': {   'description': 'Gun-truck '
                                                                           'with '
                                                                           'a '
                                                                           'rusted '
                                                                           'turret '
                                                                           'preaching '
                                                                           'from '
                                                                           'the '
                                                                           'bed.',
                                                            'name': 'Pulpit '
                                                                    'Cannon'}},
                         'units': [   'RaiderBuggy',
                                      'RustySedan',
                                      'RustBucket',
                                      'Technical']},
    'sanctum_eternal': {   'control': 100,
                           'description': 'Solemn wardens of the last running '
                                          'engine, maintaining holy neutrality '
                                          'so all pilgrims may approach the '
                                          'sacred idle.',
                           'faction_boss': None,
                           'hub_city_coordinates': (0, 0),
                           'name': 'The Sanctum Eternal',
                           'relationships': {   'crimson_litany': 'Neutral',
                                                'iron_choir': 'Neutral',
                                                'rust_prophets': 'Neutral',
                                                'shattered_glass_order': 'Neutral'},
                           'unit_names': {   'GuardTruck': {   'description': 'Armored '
                                                                              'shrine-truck '
                                                                              'blocking '
                                                                              'the '
                                                                              'road '
                                                                              'to '
                                                                              'the '
                                                                              'sacred '
                                                                              'engine.',
                                                               'name': 'Reliquary '
                                                                       'Gate'},
                                             'Peacekeeper': {   'description': 'Patrol '
                                                                               'car '
                                                                               'circling '
                                                                               'the '
                                                                               'cathedral '
                                                                               'grounds '
                                                                               'in '
                                                                               'silent '
                                                                               'vigil.',
                                                                'name': 'Vestibule '
                                                                        'Watch'}},
                           'units': ['GuardTruck', 'Peacekeeper']},
    'shattered_glass_order': {   'control': 45,
                                 'description': 'Monastic collectors of '
                                                'stained glass shards, '
                                                'believing each fragment holds '
                                                "a dead saint's final memory.",
                                 'faction_boss': {   'damage_multiplier': 2.0,
                                                     'hp_multiplier': 4.5,
                                                     'name': 'Abbot Prismatica',
                                                     'vehicle': 'ArmoredTruck'},
                                 'hub_city_coordinates': (4, 5),
                                 'name': 'The Shattered Glass Order',
                                 'relationships': {   'crimson_litany': 'Wary',
                                                      'iron_choir': 'Friendly',
                                                      'rust_prophets': 'Hostile',
                                                      'sanctum_eternal': 'Neutral'},
                                 'unit_names': {   'ArmoredTruck': {   'description': 'Glass-armored '
                                                                                      'vault '
                                                                                      'on '
                                                                                      'wheels '
                                                                                      'carrying '
                                                                                      'irreplaceable '
                                                                                      'saint '
                                                                                      'fragments.',
                                                                       'name': 'Reliquary '
                                                                               'Hauler'},
                                                   'Miner': {   'description': 'Heavy '
                                                                               'excavator '
                                                                               'that '
                                                                               'cracks '
                                                                               'open '
                                                                               'petrified '
                                                                               'churches '
                                                                               'for '
                                                                               'glass '
                                                                               'within.',
                                                                'name': 'Cathedral '
                                                                        'Breaker'},
                                                   'RustySedan': {   'description': 'Battered '
                                                                                    'sedan '
                                                                                    'whose '
                                                                                    'windshield '
                                                                                    'is '
                                                                                    'a '
                                                                                    'mosaic '
                                                                                    'of '
                                                                                    'colored '
                                                                                    'glass.',
                                                                     'name': 'Shard '
                                                                             'Pilgrim'}},
                                 'units': [   'ArmoredTruck',
                                              'RustySedan',
                                              'Miner']}}
