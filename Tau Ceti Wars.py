import os
import sys
import math
import pygame
import game_template
from OpenGL.GL import *
from OpenGL.GLU import *
from pygame.locals import *

# Módulos novos
from core.models import PlanetaData, load_planets
from core.graphics_utils import load_background, load_texture
from core.renderer import draw_ring, draw_background, draw_sphere, draw_fade_overlay, draw_tooltip

# prepara a cena e as regras de renderização 3D.
def start_opengl(height, width):
    # define a área exata da tela
    glViewport(0, 0, int(width), int(height))

    # define a perspectiva (câmera)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    
    # parâmetros: FOV (45 graus), Aspect Ratio (largura/altura), Near Clipping Plane, Far Clipping Plane
    # tudo que estiver mais perto que 0.1 ou mais longe que 1000 não será renderizado
    gluPerspective(45, (width / height), 0.1, 1000.0)
    
    # retorna para a matriz de visualização de modelos
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    
    # afasta a câmera no eixo Z para podermos ver o centro do espaço
    glTranslatef(0.0, 0.0, -50.0)
    
    # ativa o Z-Buffer (teste de profundidade)
    # fundamental para que modelos 3D não sejam desenhados de dentro para fora
    glEnable(GL_DEPTH_TEST)

    # suporte de canal alpha (transparência)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

def main():
    # inicialização do pygame
    pygame.init()

    # incialização de fonte
    pygame.font.init() # Inicializa o renderizador de fontes
    fonte_tooltip = pygame.font.SysFont('Arial', 24, bold=True)

    # obtém as informações do monitor atual
    screen_info = pygame.display.Info()
    screen_height = screen_info.current_h
    screen_width = screen_info.current_w

    screen = pygame.display.set_mode((screen_width, screen_height), DOUBLEBUF | OPENGL)
    pygame.display.set_caption("Tau Ceti Wars")

    start_opengl(screen_height, screen_width)

    # relógio para controle de fps
    clock = pygame.time.Clock()
    FPS = 60

    # pega o diretório do arquivo .py atual
    script_path = os.path.dirname(os.path.abspath(__file__))

    # pega o diretório com o nome do arquivo json
    json_path = os.path.join(script_path, 'planetas.json')
    
    print(f"\nBuscando arquivo json em:\n-> {json_path}")

    # carrega planetas no diretório encontrado
    star_system = load_planets(json_path)

    # se a lista estiver vazia, encerra o jogo
    if not star_system:
        print("\nA lista de planetas está vazia ou o arquivo não foi lido.")
        pygame.quit()
        sys.exit()
        
    # se o arquivo foi carregado, imprime os planetas lidos
    print("\nPlanetas carregados:")
    for planeta in star_system:
        print(f" -> {planeta.name} (Tamanho: {planeta.size} | Cor: {planeta.color_or_texture})")

    # --- CORREÇÃO DE CARREGAMENTO DE ASSETS ---
    # Agora usamos o script_path como base e os caminhos relativos do JSON
    for planet in star_system:
        # verifica se o campo parece ser um arquivo de imagem
        if planet.color_or_texture.lower().endswith(('.png', '.jpg', '.jpeg')):
            image_path = os.path.join(script_path, planet.color_or_texture)
            planet.texture_id = load_texture(image_path)
            status = f"Textura carregada (ID {planet.texture_id})" if planet.texture_id else f"FALHA: {image_path}"
            print(f" -> {planet.name}: {status}")
        else:
            print(f" -> {planet.name}: Usando cor sólida ({planet.color_or_texture})")

        # carrega as splash arts dos planetas usando o caminho do JSON
        if planet.splash_image:
            splash_path = os.path.join(script_path, planet.splash_image)
            planet.splash_texture_id = load_background(splash_path, screen_width, screen_height)

    # caminho da textura do anel (ajustado para a sua pasta Assets)
    ring_image_path = os.path.join(script_path, 'Assets', 'Planet Texture', 'anel.png')
    ring_texture_id = load_texture(ring_image_path)

    if ring_texture_id:
        print(" -> Textura dos aneis planetários carregada com sucesso!")
    else:
        print(f" -> ATENÇÃO: Textura '{ring_image_path}' não encontrada")

    # caminho da textura de fundo (ajustado para a sua pasta Assets)
    background_image_path = os.path.join(script_path, 'Assets', 'Backgrounds', 'fundo_espacial.png')
    background_texture_id = load_background(background_image_path, screen_width, screen_height)

    if background_texture_id:
        print(" -> Textura de fundo carregada com sucesso!")
    else:
        print(f" -> ATENÇÃO: Textura '{background_image_path}' não encontrada")

    # posições em que cada planeta vai ficar na cena
    planet_positions = [
        (-30.0, -10.0, 0.0), # Slot 1: fundo esquerda, mais baixo
        (-15.0,  -5.0, 0.0), # Slot 2
        (  0.0,   0.0, 0.0), # Slot 3: centro exato da tela
        ( 15.0,   5.0, 0.0), # Slot 4
        ( 30.0,  10.0, 0.0)  # Slot 5: frente direita, mais alto
    ]

    for i, planet in enumerate(star_system):
        if i < len(planet_positions):
            planet.pos_x, planet.pos_y, planet.pos_z = planet_positions[i]
        else:
            print(f"Aviso: Não há slots de posição suficientes para {planet.name}.")

    # progresso linear: desbloqueia apenas o primeiro planeta inicialmente
    if star_system:
        star_system[0].is_unlocked = True

    # variaveis de controle de camera
    cam_x, cam_y, cam_z = 0.0, 0.0, -50.0

    # velocidade da câmera durante a transição
    cam_speed = 0.015
    
    # variaveis da maquina de estados da transicao
    # estados: IDLE, PULLBACK, APPROACH, FADE_OUT, SPLASH, START_LEVEL
    transition_state = "IDLE" 
    target_planet = None
    fade_alpha = 0.0
    splash_timer = 0

    # variável de controle do loop de jogo
    running = True

    while running:
        
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                running = False
            
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_ESCAPE:
                    running = False
                
                if evento.key == pygame.K_k:
                    for planet in star_system:
                        planet.is_unlocked = True
                    print("\nTodos os planetas foram desbloqueados")
            
            # detecta o clique do mouse no planeta
            if evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 1:
                # so permite clicar se estiver livre (IDLE), tiver um planeta no foco, e ele for desbloqueado
                if transition_state == "IDLE" and focused_planet and focused_planet.is_unlocked:
                    target_planet = focused_planet
                    transition_state = "PULLBACK"

        # lógicas de estados de transição
        if transition_state == "PULLBACK":
            # Movimento simultâneo: Recua (Z) e Centraliza (X e Y) ao mesmo tempo.
            # Como usamos interpolação (cam_speed), isso cria um arco suave.
            target_z = -60.0
            target_x = -target_planet.pos_x
            target_y = -target_planet.pos_y
            
            cam_x += (target_x - cam_x) * cam_speed
            cam_y += (target_y - cam_y) * cam_speed
            cam_z += (target_z - cam_z) * cam_speed
            
            # quando estiver quase no ponto máximo de recuo e centralizado, vai para a frente
            if abs(cam_z - target_z) < 0.5 and abs(cam_x - target_x) < 0.5:
                transition_state = "APPROACH"
                
        elif transition_state == "APPROACH":
            # vai na direção do planeta alvo
            target_z = -target_planet.pos_z - (target_planet.size * 3.5) 
            cam_z += (target_z - cam_z) * cam_speed
            
            # verifica se a distância até o planeta é menor que 15 unidades
            distancia_restante = abs(cam_z - target_z)
            if distancia_restante < 15.0:
                fade_alpha += 0.03 # um pouco mais rápido para fechar antes de bater
                
                # quando a tela fica 100% preta, passa para a arte
                if fade_alpha >= 1.0:
                    fade_alpha = 1.0
                    transition_state = "SPLASH_FADE_IN"
                
        elif transition_state == "SPLASH_FADE_IN":
            # reduz o alpha do quadrado preto para revelar a arte suavemente.
            fade_alpha -= 0.02
            
            if fade_alpha <= 0.0:
                fade_alpha = 0.0
                transition_state = "SPLASH_WAIT"
                splash_timer = pygame.time.get_ticks() # começa a contar tempo de "loading" aqui
                
        elif transition_state == "SPLASH_WAIT":
            # aguarda o tempo da arte da transição
            current_time = pygame.time.get_ticks()
            if current_time - splash_timer > 3000:
                transition_state = "START_LEVEL"
                
        elif transition_state == "START_LEVEL":
            print(f"\nIniciando fase: {target_planet.name}!")
            
            # chama a fase escolhida
            resultado_fase = game_template.start(target_planet.name)
            
            # retorno da fase para menu
            print(f"\nFase concluída: {target_planet.name}!")
            
            # reseta todas as variáveis de visualização
            start_opengl(screen_height, screen_width)
            transition_state = "IDLE"
            fade_alpha = 0.0
            target_planet = None
            cam_x, cam_y, cam_z = 0.0, 0.0, -50.0
            
            # destrava o mouse
            pygame.mouse.set_visible(True)
            pygame.event.set_grab(False)

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        # Desenha o fundo espacial
        if background_texture_id:
            draw_background(background_texture_id)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity() 
        
        # variáveis de movimento da câmera
        glTranslatef(cam_x, cam_y, cam_z) 

        mouse_x, mouse_y = pygame.mouse.get_pos()
        modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
        projection = glGetDoublev(GL_PROJECTION_MATRIX)
        viewport = glGetIntegerv(GL_VIEWPORT)

        focused_planet = None

        for planet in star_system:
            planet.current_angle += planet.rotation_speed
            if planet.current_angle >= 360.0:
                planet.current_angle -= 360.0

            # o mouse picking so funciona se o jogador nao estiver no meio de qualquer transição 
            if transition_state == "IDLE":
                try:
                    win_x, win_y, win_z = gluProject(planet.pos_x, planet.pos_y, planet.pos_z, 
                                                     modelview, projection, viewport)
                    x_limit, _, _ = gluProject(planet.pos_x + planet.size, planet.pos_y, planet.pos_z, 
                                               modelview, projection, viewport)
                    screen_radius = abs(x_limit - win_x)
                    win_y_inverted = screen_height - win_y
                    distance = math.hypot(mouse_x - win_x, mouse_y - win_y_inverted)

                    if distance < screen_radius:
                        focused_planet = planet
                except (ValueError, OpenGL.GLU.GLUerror):
                    pass 

            glPushMatrix() 
            glTranslatef(planet.pos_x, planet.pos_y, planet.pos_z) 
            glRotatef(-90.0, 1, 0, 0)
            glRotatef(planet.axis_tilt, 1, 0, 0) 

            # Desenha os anéis se o planeta possuir
            if planet.has_rings:
                draw_ring(planet.size * 1.2, planet.size * 1.9, ring_texture_id)

            glRotatef(planet.current_angle, 0, 0, 1)
            # Desenha a esfera do planeta
            draw_sphere(planet.size, planet.color_or_texture, planet.texture_id)
            glPopMatrix() 

        # desenha a UI apenas se estiver parado e com o mouse em cima
        if focused_planet and transition_state == "IDLE":
            if focused_planet.is_unlocked:
                texto_ui = focused_planet.name
                cor_texto = (255, 255, 255) # branco para liberado
            else:
                texto_ui = f"{focused_planet.name} (BLOQUEADO)"
                cor_texto = (255, 80, 80) # vermelho suave para bloqueado
                
            draw_tooltip(texto_ui, mouse_x, mouse_y, screen_width, screen_height, fonte_tooltip, cor_texto)

        # máquina de estados visuais de transição (Splash Art)
        if transition_state in ["SPLASH_FADE_IN", "SPLASH_WAIT"]:
            if target_planet and target_planet.splash_texture_id:
                draw_background(target_planet.splash_texture_id)

        # Overlay de fade (transição suave para o preto)
        if fade_alpha > 0.0:
            draw_fade_overlay(screen_width, screen_height, fade_alpha)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()