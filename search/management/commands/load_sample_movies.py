"""
Loads a curated set of 45 well-known films with rich descriptions.
Designed to showcase SoClose's semantic search across a variety of query types:
  • Vague vibes ("something melancholy but hopeful")
  • Scene memory ("movie with a famous shower scene")
  • Character recall ("film with a manipulative chess player")
  • Dialogue ("movie where someone says we accept the love we think we deserve")
  • Visual style ("neon-lit city at night, 80s aesthetic")
"""

from django.core.management.base import BaseCommand

from search.models import Movie

SAMPLE_MOVIES = [
    {
        "title": "Inception",
        "tagline": "Your mind is the scene of the crime.",
        "synopsis": (
            "A skilled thief who steals corporate secrets through dream-sharing technology "
            "is given the inverse task of planting an idea into the mind of a C.E.O. "
            "He assembles a team and dives into layered dreamscapes, each level deeper "
            "and more surreal than the last, racing against time before the dream collapses."
        ),
        "genre": "Sci-Fi, Thriller",
        "cast": "Leonardo DiCaprio, Joseph Gordon-Levitt, Elliot Page, Tom Hardy, Ken Watanabe",
        "director": "Christopher Nolan",
        "release_year": 2010,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/9gk7adHYeDvHkCSEqAvQNLV5Uge.jpg",
    },
    {
        "title": "The Shawshank Redemption",
        "tagline": "Fear can hold you prisoner. Hope can set you free.",
        "synopsis": (
            "Two imprisoned men bond over several decades, finding solace and eventual "
            "redemption through acts of common decency. Andy Dufresne, a banker wrongly "
            "convicted of murder, befriends lifer Ellis Boyd 'Red' Redding and quietly "
            "transforms life inside Shawshank Prison, while never abandoning the hope "
            "of freedom."
        ),
        "genre": "Drama",
        "cast": "Tim Robbins, Morgan Freeman, Bob Gunton, William Sadler",
        "director": "Frank Darabont",
        "release_year": 1994,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/q6y0Go1tsGEsmtFryDOJo3dEmqu.jpg",
    },
    {
        "title": "Parasite",
        "tagline": "Act like you own the place.",
        "synopsis": (
            "A poor Korean family schemes to become employed by a wealthy family, each "
            "member posing as an unrelated, highly qualified individual. Tension mounts "
            "when dark secrets hidden beneath the rich family's home are unearthed, "
            "leading to a shocking, violent confrontation about class inequality and "
            "the nature of wealth."
        ),
        "genre": "Thriller, Drama, Dark Comedy",
        "cast": "Song Kang-ho, Lee Sun-kyun, Cho Yeo-jeong, Choi Woo-shik, Park So-dam",
        "director": "Bong Joon-ho",
        "release_year": 2019,
        "language": "Korean",
        "poster_url": "https://image.tmdb.org/t/p/w500/7IiTTgloJzvGI1TAYymCfbfl3vT.jpg",
    },
    {
        "title": "Eternal Sunshine of the Spotless Mind",
        "tagline": "You can erase someone from your mind. Getting them out of your heart is another story.",
        "synopsis": (
            "When their relationship turns sour, a couple undergoes a medical procedure "
            "to have each other erased from their memories. As Joel's memories of Clementine "
            "begin to fade, he desperately tries to hold on to their shared moments from "
            "within the dream. A bittersweet meditation on love, loss, and why painful "
            "memories make us who we are."
        ),
        "genre": "Romance, Sci-Fi, Drama",
        "cast": "Jim Carrey, Kate Winslet, Tom Wilkinson, Kirsten Dunst, Mark Ruffalo",
        "director": "Michel Gondry",
        "release_year": 2004,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/5MwkWH9tYHv3mV9OqYdjuDEam4x.jpg",
    },
    {
        "title": "Interstellar",
        "tagline": "Mankind was born on Earth. It was never meant to die here.",
        "synopsis": (
            "A team of explorers travels through a wormhole in space in an attempt to "
            "ensure humanity's survival. Cooper, a former NASA pilot turned farmer, "
            "leaves his family behind to lead the mission, navigating black holes, time "
            "dilation, and the limits of human endurance. A deeply emotional story about "
            "a father's love stretched across the cosmos."
        ),
        "genre": "Sci-Fi, Adventure, Drama",
        "cast": "Matthew McConaughey, Anne Hathaway, Jessica Chastain, Michael Caine, Matt Damon",
        "director": "Christopher Nolan",
        "release_year": 2014,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg",
    },
    {
        "title": "Pulp Fiction",
        "tagline": "Just because you are a character doesn't mean you have character.",
        "synopsis": (
            "The lives of two mob hitmen, a boxer, a gangster and his wife, and a pair of "
            "diner bandits interweave in four tales of violence and redemption. Told in "
            "a nonlinear narrative with razor-sharp dialogue, unexpected humor, and iconic "
            "scenes — from a Royale with Cheese conversation to a dance at Jack Rabbit Slim's."
        ),
        "genre": "Crime, Drama",
        "cast": "John Travolta, Uma Thurman, Samuel L. Jackson, Bruce Willis, Harvey Keitel",
        "director": "Quentin Tarantino",
        "release_year": 1994,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/d5iIlFn5s0ImszYzBPb8JPIfbXD.jpg",
    },
    {
        "title": "The Perks of Being a Wallflower",
        "tagline": "We accept the love we think we deserve.",
        "synopsis": (
            "An introverted and socially awkward teenager navigates his freshman year of "
            "high school, finding friendship and love among a group of free-spirited seniors. "
            "Charlie, who has a troubled past, begins writing letters to an anonymous friend "
            "as he slowly opens himself up to the world, to mixtapes, Rocky Horror, and "
            "to understanding why we accept the love we think we deserve."
        ),
        "genre": "Drama, Romance",
        "cast": "Logan Lerman, Emma Watson, Ezra Miller, Paul Rudd",
        "director": "Stephen Chbosky",
        "release_year": 2012,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/3tTMOBQMBVF0ym9hLRBBzW6LCUC.jpg",
    },
    {
        "title": "Psycho",
        "tagline": "Check in. Relax. Take a shower.",
        "synopsis": (
            "A secretary embezzles money from her employer's client and goes on the run, "
            "ending up at the remote Bates Motel run by the shy, awkward Norman Bates. "
            "The film's infamous shower scene, shot in 70 cuts over 45 seconds, changed "
            "cinema forever. A masterpiece of suspense, voyeurism, and psychological horror."
        ),
        "genre": "Horror, Thriller",
        "cast": "Anthony Perkins, Janet Leigh, Vera Miles, John Gavin",
        "director": "Alfred Hitchcock",
        "release_year": 1960,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/yz4QVqPx3h1hD1DfqqQkCq3rmxW.jpg",
    },
    {
        "title": "Blade Runner 2049",
        "tagline": "The key to the future is finally unearthed.",
        "synopsis": (
            "A young blade runner discovers a long-buried secret that has the potential "
            "to plunge what's left of society into chaos. His discovery leads him on a "
            "quest to find Rick Deckard, a former blade runner who's been missing for "
            "thirty years. Breathtaking neon-lit desert vistas and flooded cities "
            "create a hauntingly beautiful dystopian world."
        ),
        "genre": "Sci-Fi, Drama, Neo-Noir",
        "cast": "Ryan Gosling, Harrison Ford, Ana de Armas, Sylvia Hoeks, Jared Leto",
        "director": "Denis Villeneuve",
        "release_year": 2017,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/gajva2L0rPYkEWjzgFlBXCAVBE5.jpg",
    },
    {
        "title": "Amélie",
        "tagline": "One girl's quest to improve everyone else's life.",
        "synopsis": (
            "Amélie is an imaginative girl who lives quietly in Montmartre. When she "
            "discovers a child's old treasure box hidden in her apartment wall, she "
            "decides to dedicate her life to bringing happiness to those around her. "
            "A whimsical, visually inventive fairy tale about a shy romantic who finds "
            "joy in small, magical details of everyday Parisian life."
        ),
        "genre": "Romance, Comedy, Fantasy",
        "cast": "Audrey Tautou, Mathieu Kassovitz, Rufus, Lorella Cravotta",
        "director": "Jean-Pierre Jeunet",
        "release_year": 2001,
        "language": "French",
        "poster_url": "https://image.tmdb.org/t/p/w500/ftODZXaXral5GpfOPnq5HBhGqpT.jpg",
    },
    {
        "title": "Whiplash",
        "tagline": "The road to greatness can take you to the edge.",
        "synopsis": (
            "A promising young jazz drummer enrolls at a music conservatory and comes "
            "under the tutelage of an abusive, manipulative instructor who pushes him "
            "beyond the limits of his ability in search of greatness. A brutal, "
            "electrifying battle of wills exploring the price of obsession and "
            "the line between inspiration and abuse."
        ),
        "genre": "Drama, Music",
        "cast": "Miles Teller, J.K. Simmons, Melissa Benoist, Paul Reiser",
        "director": "Damien Chazelle",
        "release_year": 2014,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/7fn624j5lj3xTme2SgiLCeuedmO.jpg",
    },
    {
        "title": "Her",
        "tagline": "A love story for the future.",
        "synopsis": (
            "In a near future Los Angeles, a lonely, introverted man falls in love with "
            "an artificially intelligent operating system with a feminine voice and "
            "evolving personality. As the relationship deepens, Theodore must confront "
            "what it means to love, to connect, and to be human in a world of "
            "frictionless technology and curated loneliness."
        ),
        "genre": "Romance, Sci-Fi, Drama",
        "cast": "Joaquin Phoenix, Scarlett Johansson, Amy Adams, Rooney Mara",
        "director": "Spike Jonze",
        "release_year": 2013,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/eCOtqtfvn7mxGaFxDqmrUJnmgck.jpg",
    },
    {
        "title": "The Queen's Gambit",
        "tagline": "The only place she ever felt at home.",
        "synopsis": (
            "An orphaned chess prodigy rises from a Kentucky orphanage in the 1950s "
            "to become a world chess champion, battling sexism, addiction, and her "
            "own demons along the way. Beth Harmon's singular genius at the chessboard "
            "is matched only by her self-destructive tendencies and relentless ambition."
        ),
        "genre": "Drama",
        "cast": "Anya Taylor-Joy, Bill Camp, Moses Ingram, Thomas Brodie-Sangster",
        "director": "Scott Frank",
        "release_year": 2020,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/zU0htwkhNvBQdVSIKB9s6hgVeFK.jpg",
    },
    {
        "title": "Spirited Away",
        "tagline": "The tunnel led Chihiro to a magical world.",
        "synopsis": (
            "During her family's move to the suburbs, a sulky ten-year-old girl wanders "
            "into a world ruled by gods, witches, and spirits, where humans are changed "
            "into beasts. To rescue her parents, she must work in a supernatural bathhouse, "
            "befriending a mysterious boy named Haku and learning the value of hard work, "
            "loyalty, and identity."
        ),
        "genre": "Animation, Fantasy, Adventure",
        "cast": "Daveigh Chase, Suzanne Pleshette, Miyu Irino, Jason Marsden",
        "director": "Hayao Miyazaki",
        "release_year": 2001,
        "language": "Japanese",
        "poster_url": "https://image.tmdb.org/t/p/w500/39wmItIWsg5sZMyRUHLkWBcuVCM.jpg",
    },
    {
        "title": "La La Land",
        "tagline": "Here's to the ones who dream.",
        "synopsis": (
            "A jazz musician and an aspiring actress fall in love while pursuing their "
            "dreams in Los Angeles. Their romance is set against the backdrop of tap "
            "dancing on a hilltop, watching the stars from Griffith Observatory, and "
            "late nights in smoky jazz clubs. A bittersweet musical about sacrifice, "
            "ambition, and the road not taken."
        ),
        "genre": "Romance, Musical, Drama",
        "cast": "Ryan Gosling, Emma Stone, John Legend, J.K. Simmons",
        "director": "Damien Chazelle",
        "release_year": 2016,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/uDO8zWDhfWwoFdKS4fzkUJt0Rf0.jpg",
    },
    {
        "title": "Arrival",
        "tagline": "Why are they here?",
        "synopsis": (
            "When mysterious spacecraft touch down across the globe, an elite team is "
            "put together to investigate. A linguist and a theoretical physicist must "
            "decode the aliens' non-linear language, which begins to alter the linguist's "
            "perception of time. A quiet, cerebral science fiction film about grief, "
            "communication, and the nature of time as a circle."
        ),
        "genre": "Sci-Fi, Drama, Mystery",
        "cast": "Amy Adams, Jeremy Renner, Forest Whitaker, Michael Stuhlbarg",
        "director": "Denis Villeneuve",
        "release_year": 2016,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/x2FJsf1ElAgr63Y3PNPtJrcmpoe.jpg",
    },
    {
        "title": "Mulholland Drive",
        "tagline": "A love story in the city of dreams.",
        "synopsis": (
            "A bright-eyed aspiring actress arrives in Hollywood only to find her "
            "plans complicated by a mysterious amnesiac woman she encounters in her "
            "aunt's apartment. Their intertwined fates spiral into a surreal, dreamlike "
            "mystery of identity, desire, jealousy, and delusion set against the dark "
            "side of Hollywood glamour."
        ),
        "genre": "Mystery, Drama, Neo-Noir",
        "cast": "Naomi Watts, Laura Harring, Justin Theroux, Ann Miller",
        "director": "David Lynch",
        "release_year": 2001,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/wQPpGJBUGGYfn5VtSnVnfkBCwj2.jpg",
    },
    {
        "title": "The Social Network",
        "tagline": "You don't get to 500 million friends without making a few enemies.",
        "synopsis": (
            "The founding of Facebook told through legal battles as Mark Zuckerberg "
            "is sued by former friends and collaborators. A story of ambition, betrayal, "
            "and the price of obsessive genius, told at blistering pace through razor-sharp "
            "Aaron Sorkin dialogue. One of the defining films of the internet age."
        ),
        "genre": "Drama, Biography",
        "cast": "Jesse Eisenberg, Andrew Garfield, Justin Timberlake, Rooney Mara",
        "director": "David Fincher",
        "release_year": 2010,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/n0ybibhJtQ5icDqTp8eRytcIHJx.jpg",
    },
    {
        "title": "Lost in Translation",
        "tagline": "Everyone wants to be found.",
        "synopsis": (
            "A faded movie star and a neglected young woman form an unlikely bond in "
            "Tokyo's Park Hyatt Hotel. Jetlagged and alienated by the neon-lit city "
            "around them, Bob and Charlotte share whisky, karaoke, and a quiet, "
            "melancholy connection that neither can fully name. A gentle meditation "
            "on loneliness and fleeting human connection."
        ),
        "genre": "Drama, Romance",
        "cast": "Bill Murray, Scarlett Johansson, Giovanni Ribisi, Anna Faris",
        "director": "Sofia Coppola",
        "release_year": 2003,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/jiGP6rUKy0Z4HUF1kzp7j5JLeak.jpg",
    },
    {
        "title": "Moonlight",
        "tagline": "This is the story of a lifetime.",
        "synopsis": (
            "A young African-American man grapples with his identity and sexuality "
            "across three defining chapters of his life: boyhood, adolescence, and "
            "adulthood. Set in a rough Miami neighborhood, the film is told in three "
            "acts following Chiron, a sensitive boy raised by a crack-addicted mother "
            "and mentored by a local drug dealer. Hauntingly beautiful and deeply tender."
        ),
        "genre": "Drama",
        "cast": "Mahershala Ali, Naomie Harris, Trevante Rhodes, André Holland",
        "director": "Barry Jenkins",
        "release_year": 2016,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/4911T5FbJ9eAlntig4Gu7K4Mz9l.jpg",
    },
    {
        "title": "Get Out",
        "tagline": "Just because you're invited doesn't mean you're welcome.",
        "synopsis": (
            "A young African-American man visits his white girlfriend's family estate "
            "and becomes increasingly unsettled by the odd behavior of the residents "
            "and staff. As the weekend progresses, a series of disturbing discoveries "
            "lead him to a truth more terrifying than he imagined. A sharp horror satire "
            "on racism, privilege, and the uncanny in liberal white America."
        ),
        "genre": "Horror, Thriller",
        "cast": "Daniel Kaluuya, Allison Williams, Bradley Whitford, Catherine Keener",
        "director": "Jordan Peele",
        "release_year": 2017,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/tFXcEccSQMf3lfhfXKSU9iRBpa3.jpg",
    },
    {
        "title": "Everything Everywhere All at Once",
        "tagline": "The universe is so much bigger than you realize.",
        "synopsis": (
            "A middle-aged Chinese-American laundromat owner is swept into a ludicrous "
            "adventure where she alone can save the multiverse by connecting with the lives "
            "she could have led in other universes. Beneath the chaos of googly eyes, "
            "hot dog fingers, and martial arts, the film is a profound story about a "
            "mother and daughter and intergenerational love."
        ),
        "genre": "Sci-Fi, Action, Comedy, Drama",
        "cast": "Michelle Yeoh, Ke Huy Quan, Stephanie Hsu, Jamie Lee Curtis, James Hong",
        "director": "Daniel Kwan, Daniel Scheinert",
        "release_year": 2022,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/w3LxiVYdWWRvEVdn5RYq6jIqkb1.jpg",
    },
    {
        "title": "Portrait of a Lady on Fire",
        "tagline": "Do all lovers feel they are inventing something?",
        "synopsis": (
            "On an isolated island in Brittany at the end of the eighteenth century, "
            "a female painter is commissioned to paint a wedding portrait of a young "
            "woman who is about to be married against her will. A slow-burning, intensely "
            "felt love story between two women told through glances, silences, and a "
            "portrait that captures more than just a likeness."
        ),
        "genre": "Romance, Drama",
        "cast": "Noémie Merlant, Adèle Haenel, Luàna Bajrami, Valeria Golino",
        "director": "Céline Sciamma",
        "release_year": 2019,
        "language": "French",
        "poster_url": "https://image.tmdb.org/t/p/w500/3NTAbAiao4JLzFsBE6jVNUsEDv4.jpg",
    },
    {
        "title": "Drive",
        "tagline": "There are no clean getaways.",
        "synopsis": (
            "A Hollywood stunt driver who moonlights as a getaway driver for criminals "
            "becomes romantically involved with his neighbor and agrees to help her "
            "husband rob a pawn shop. When the job goes wrong, he finds himself "
            "hunted by dangerous criminals. Set against neon-drenched Los Angeles nights, "
            "a slow-burn neo-noir with sudden, explosive violence."
        ),
        "genre": "Crime, Drama, Neo-Noir",
        "cast": "Ryan Gosling, Carey Mulligan, Bryan Cranston, Albert Brooks, Ron Perlman",
        "director": "Nicolas Winding Refn",
        "release_year": 2011,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/602vevIURmpjn9kZH5e5ZGJAYAO.jpg",
    },
    {
        "title": "Hereditary",
        "tagline": "What is in your blood.",
        "synopsis": (
            "After the matriarch of the Graham family passes away, her daughter's family "
            "begins to unravel cryptic and terrifying secrets about their ancestry. "
            "What starts as grief turns into something far more sinister as the family "
            "is torn apart by supernatural forces tied to their grandmother's secret cult."
        ),
        "genre": "Horror, Drama",
        "cast": "Toni Collette, Gabriel Byrne, Alex Wolff, Milly Shapiro, Ann Dowd",
        "director": "Ari Aster",
        "release_year": 2018,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/4OTONHaVHoWbNzBN1b5Jlm5k5hU.jpg",
    },
    {
        "title": "Brokeback Mountain",
        "tagline": "Love is a force of nature.",
        "synopsis": (
            "Two young men — a ranch hand and a rodeo cowboy — meet in the summer of 1963 "
            "herding sheep on the remote Brokeback Mountain in Wyoming. Their unexpected "
            "relationship evolves into a lifelong love affair with devastating consequences "
            "for both men, their families, and the choices they are forced to make."
        ),
        "genre": "Romance, Drama",
        "cast": "Heath Ledger, Jake Gyllenhaal, Anne Hathaway, Michelle Williams",
        "director": "Ang Lee",
        "release_year": 2005,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/9J3aKD8xqv4fmCE2yfN1CzKFBhk.jpg",
    },
    {
        "title": "Oldboy",
        "tagline": "Laugh and the world laughs with you. Weep and you weep alone.",
        "synopsis": (
            "After being mysteriously imprisoned for fifteen years without reason, "
            "Oh Dae-su is suddenly released and given five days to find his captor. "
            "His investigation leads him through shocking twists involving a beautiful "
            "young woman and a villain who has spent fifteen years planning revenge. "
            "Famous for its brutal corridor hammer fight."
        ),
        "genre": "Mystery, Thriller, Action",
        "cast": "Choi Min-sik, Yoo Ji-tae, Kang Hye-jung",
        "director": "Park Chan-wook",
        "release_year": 2003,
        "language": "Korean",
        "poster_url": "https://image.tmdb.org/t/p/w500/pWDtjs568ZfOTMbURQBYuT4Qxka.jpg",
    },
    {
        "title": "The Grand Budapest Hotel",
        "tagline": "A perfect concierge anticipates the needs of the guest.",
        "synopsis": (
            "The adventures of Gustave H, a legendary concierge at a famous European "
            "hotel between the wars, and Zero Moustafa, the lobby boy who becomes his "
            "most trusted friend. Together they steal — then recover — a priceless "
            "Renaissance painting, elude the clutches of a sinister family, and maintain "
            "civilization itself against the forces of barbarism."
        ),
        "genre": "Comedy, Adventure, Drama",
        "cast": "Ralph Fiennes, Tony Revolori, Saoirse Ronan, Bill Murray, Tilda Swinton",
        "director": "Wes Anderson",
        "release_year": 2014,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/eWdyYQreja6JGCzqHWXpWHDrrPo.jpg",
    },
    {
        "title": "Marriage Story",
        "tagline": "A love story about divorce.",
        "synopsis": (
            "A stage director and his actress wife struggle through a coast-to-coast "
            "divorce that pushes them both to their personal extremes. What begins as "
            "a friendly agreement to avoid lawyers escalates painfully into a bitter "
            "legal battle, while both still clearly love each other deeply. Anchored "
            "by two shattering performances."
        ),
        "genre": "Drama, Romance",
        "cast": "Adam Driver, Scarlett Johansson, Laura Dern, Alan Alda, Ray Liotta",
        "director": "Noah Baumbach",
        "release_year": 2019,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/e1BEDiMJOtOFKVQWPqJGQHc2N9R.jpg",
    },
    {
        "title": "Midsommar",
        "tagline": "Let the festivities begin.",
        "synopsis": (
            "A couple travels to Sweden to visit a rural hometown's fabled midsummer "
            "festival. What begins as an idyllic retreat quickly devolves into an "
            "increasingly violent and bizarre competition at the hands of a pagan cult. "
            "Shot in bright, unrelenting sunlight — a horror film where you can see "
            "every terrifying thing happening."
        ),
        "genre": "Horror, Drama",
        "cast": "Florence Pugh, Jack Reynor, William Jackson Harper, Vilhelm Blomgren",
        "director": "Ari Aster",
        "release_year": 2019,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/7LEI8ulZzO5gy9Ww2NVCrKmc9Bg.jpg",
    },
    {
        "title": "Knives Out",
        "tagline": "Everyone's a suspect.",
        "synopsis": (
            "A detective investigates the death of the patriarch of an eccentric, "
            "combative family. What initially looks like a suicide quickly becomes "
            "a whodunit involving the entire family, a kind-hearted nurse, and a "
            "brilliant but unorthodox detective named Benoit Blanc. A clever, witty "
            "subversion of the murder mystery genre."
        ),
        "genre": "Mystery, Comedy, Thriller",
        "cast": "Daniel Craig, Ana de Armas, Chris Evans, Jamie Lee Curtis, Toni Collette",
        "director": "Rian Johnson",
        "release_year": 2019,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/pThyQovXQrws2OKMRJnA4CJU5vq.jpg",
    },
    {
        "title": "Moonrise Kingdom",
        "tagline": "Summer. 1965.",
        "synopsis": (
            "A pair of young lovers flee their New England town, which causes a local "
            "search party to fan out and look for them. Sam and Suzy, twelve-year-olds "
            "who fall in love by mail and run away together to a secret cove, are pursued "
            "by scouts, a sheriff, and dysfunctional parents in a whimsical, melancholy "
            "story about first love and belonging."
        ),
        "genre": "Romance, Comedy, Drama",
        "cast": "Jared Gilman, Kara Hayward, Bruce Willis, Edward Norton, Bill Murray",
        "director": "Wes Anderson",
        "release_year": 2012,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/jLeHpCX6HCzrSuSKP1sjjTh2MkD.jpg",
    },
    {
        "title": "Sorry to Bother You",
        "tagline": "Don't take this the wrong way.",
        "synopsis": (
            "In a surrealist version of present-day Oakland, a young Black telemarketer "
            "discovers a magical key to success — using a 'white voice' — and is then "
            "propelled into a universe of problematic perks. A wildly original satire "
            "on capitalism, race, and the ethics of selling out."
        ),
        "genre": "Comedy, Sci-Fi, Satire",
        "cast": "Lakeith Stanfield, Tessa Thompson, Jermaine Fowler, Omari Hardwick, Armie Hammer",
        "director": "Boots Riley",
        "release_year": 2018,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/f7HfXLvMRsHm0y7tCBhM3pgxeqS.jpg",
    },
    {
        "title": "The Before Trilogy",
        "tagline": "Two strangers. One night. A conversation that lasts a lifetime.",
        "synopsis": (
            "Before Sunrise: A young American man and a French woman meet on a train "
            "and spend one magical night walking through Vienna, talking about life, love, "
            "and philosophy before their lives take them in different directions. "
            "Followed by Before Sunset and Before Midnight, tracking the same couple "
            "across decades in one of cinema's great romance trilogies."
        ),
        "genre": "Romance, Drama",
        "cast": "Ethan Hawke, Julie Delpy",
        "director": "Richard Linklater",
        "release_year": 1995,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/lHGpqTdC8xUX3V6xSFnH68JqS3g.jpg",
    },
    {
        "title": "Requiem for a Dream",
        "tagline": "Their dreams cost them everything.",
        "synopsis": (
            "Four people in Brooklyn become consumed by their individual addictions — "
            "to heroin, amphetamines, and the idea of a better life on television. "
            "Harry and his mother Sara share the same feverish dream of success, each "
            "taking wildly different paths toward destruction. A harrowing, formally "
            "dazzling descent into addiction's endgame."
        ),
        "genre": "Drama",
        "cast": "Ellen Burstyn, Jared Leto, Jennifer Connelly, Marlon Wayans",
        "director": "Darren Aronofsky",
        "release_year": 2000,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/nOd6vjEmzCT0k4VYqsA2hwyi87C.jpg",
    },
    {
        "title": "Clueless",
        "tagline": "I had an overwhelming desire to do good.",
        "synopsis": (
            "A rich, popular Beverly Hills high schooler uses her considerable social "
            "skills to guide her classmates and transform an awkward new girl into a "
            "social butterfly. Loosely based on Jane Austen's Emma, it's a witty, "
            "90s-coded comedy about fashion, friendship, and a teen girl who's clueless "
            "about love until it's right in front of her."
        ),
        "genre": "Comedy, Romance",
        "cast": "Alicia Silverstone, Paul Rudd, Brittany Murphy, Stacey Dash",
        "director": "Amy Heckerling",
        "release_year": 1995,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/fPEvzMdRgHhAhCECMLJEhmVkpjA.jpg",
    },
    {
        "title": "2001: A Space Odyssey",
        "tagline": "An epic drama of adventure and exploration.",
        "synopsis": (
            "Humanity finds a mysterious, obviously artificial object buried beneath "
            "the Lunar surface and, with the intelligent computer HAL 9000, sets off "
            "on a quest. A slow, hypnotic journey through space that ends in a surreal, "
            "trippy light-show sequence beyond Jupiter. One of cinema's most visually "
            "ambitious and philosophically ambiguous films."
        ),
        "genre": "Sci-Fi",
        "cast": "Keir Dullea, Gary Lockwood, William Sylvester, Douglas Rain",
        "director": "Stanley Kubrick",
        "release_year": 1968,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/ve72VxNqjIqBlG8TfpzFqrB3uyI.jpg",
    },
    {
        "title": "Inside Out",
        "tagline": "Meet the little voices inside your head.",
        "synopsis": (
            "After young Riley is uprooted from her Midwest life and moved to San Francisco, "
            "her emotions — Joy, Fear, Anger, Disgust, and Sadness — conflict on how best "
            "to navigate a new city, house, and school. When Joy and Sadness are accidentally "
            "swept into the far reaches of Riley's mind, the remaining emotions struggle "
            "to keep Riley's life from falling apart."
        ),
        "genre": "Animation, Comedy, Drama",
        "cast": "Amy Poehler, Phyllis Smith, Bill Hader, Lewis Black, Mindy Kaling",
        "director": "Pete Docter",
        "release_year": 2015,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/aAmfIX3TT40zUHGcCKrlOZRKC7u.jpg",
    },
    {
        "title": "The Lobster",
        "tagline": "A love story for our times.",
        "synopsis": (
            "In a dystopian future, single people must find a romantic partner within "
            "45 days or be transformed into an animal of their choice. David, recently "
            "dumped by his wife, checks into a hotel where he must follow the rules — "
            "then escapes to the woods to join a rebel group called the Loners, "
            "where romance is strictly forbidden. A darkly comic satire on modern love."
        ),
        "genre": "Sci-Fi, Romance, Dark Comedy",
        "cast": "Colin Farrell, Rachel Weisz, Léa Seydoux, Ben Whishaw, John C. Reilly",
        "director": "Yorgos Lanthimos",
        "release_year": 2015,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/qEp8lEFedUWBhAh5bZrFalWRJuU.jpg",
    },
    {
        "title": "Promising Young Woman",
        "tagline": "She had it all figured out.",
        "synopsis": (
            "A young woman, traumatized by a tragedy in her past, seeks out revenge "
            "against those who crossed her path. By day she works in a coffee shop; "
            "by night she frequents bars and clubs, allowing drunk men to take her "
            "home — only to reveal she is completely sober. A candy-colored revenge "
            "thriller about rape culture, complicity, and justice."
        ),
        "genre": "Thriller, Drama",
        "cast": "Carey Mulligan, Bo Burnham, Alison Brie, Clancy Brown, Jennifer Coolidge",
        "director": "Emerald Fennell",
        "release_year": 2020,
        "language": "English",
        "poster_url": "https://image.tmdb.org/t/p/w500/o3oUErnuVMILbITVMkHhJ5RrXNr.jpg",
    },
]


class Command(BaseCommand):
    help = "Load a curated sample movie dataset into the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing movies first (use with caution).",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            deleted, _ = Movie.objects.all().delete()
            self.stdout.write(f"Cleared {deleted} existing movies.")

        created_count = 0
        updated_count = 0

        for data in SAMPLE_MOVIES:
            movie, created = Movie.objects.update_or_create(
                title=data["title"],
                defaults=data,
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Done. {created_count} movies created, {updated_count} updated.\n"
                f"  Next step: python manage.py embed_movies"
            )
        )
