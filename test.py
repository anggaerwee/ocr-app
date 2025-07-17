import chess

def print_board(board):
    print(board)

def main():
    board = chess.Board()
    while not board.is_game_over():
        print_board(board)
        print("Masukkan langkah (misalnya e2e4): ", end="")
        move_input = input().strip()
        try:
            move = chess.Move.from_uci(move_input)
            if move in board.legal_moves:
                board.push(move)
            else:
                print("Langkah tidak valid. Coba lagi.")
        except:
            print("Format salah. Gunakan format seperti e2e4.")
    
    print_board(board)
    print("Permainan selesai.")
    print("Hasil:", board.result())

if _name_ == "_main_":
    main()